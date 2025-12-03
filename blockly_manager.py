"""
Blockly Manager for LeRobot
Handles Blockly visual programming and Python code execution
"""

import asyncio
import logging
from typing import Dict, Any, Optional
import json
import time
import io
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class RobotAPI:
    """
    Real LeRobot API wrapper for Blockly programs
    Communicates with the actual robot hardware
    """
    
    def __init__(self, robot_port: Optional[str] = None):
        """
        Initialize robot API
        
        Args:
            robot_port: Serial port of the follower robot (e.g., /dev/tty_follower)
        """
        self.robot = None
        self.robot_port = robot_port
        self.positions = [0.0] * 6  # Cache for 5 DOF + gripper
        self._initialize_robot()
    
    def _initialize_robot(self):
        """Initialize the real LeRobot connection"""
        try:
            if self.robot_port:
                # Import LeRobot dynamically to avoid issues if not available
                from lerobot.common.robot_devices.motors.dynamixel import DynamixelMotorsBus
                
                logger.info(f"Initializing robot on port: {self.robot_port}")
                
                # Create motor bus for follower robot
                self.robot = DynamixelMotorsBus(
                    port=self.robot_port,
                    motors={
                        "shoulder_pan": (1, "xl330-m077"),
                        "shoulder_lift": (2, "xl330-m077"),
                        "elbow_flex": (3, "xl330-m077"),
                        "wrist_flex": (4, "xl330-m077"),
                        "wrist_roll": (5, "xl330-m077"),
                        "gripper": (6, "xl330-m077"),
                    }
                )
                self.robot.connect()
                logger.info("✅ Robot connected successfully")
                
                # Read initial positions
                self._update_positions()
            else:
                logger.warning("No robot port provided, using simulation mode")
                
        except Exception as e:
            logger.error(f"Failed to initialize robot: {e}")
            logger.warning("Falling back to simulation mode")
            self.robot = None
    
    def _update_positions(self):
        """Read current positions from robot"""
        if self.robot:
            try:
                positions = self.robot.read("Present_Position")
                for i, (name, pos) in enumerate(positions.items()):
                    if i < 6:
                        # Convert to degrees
                        self.positions[i] = float(pos)
            except Exception as e:
                logger.error(f"Error reading positions: {e}")
    
    def move_joint(self, joint: int, angle: float):
        """
        Move a specific joint to target angle
        
        Args:
            joint: Joint index (0-5: joints 1-5 + gripper)
            angle: Target angle in degrees
        """
        if joint < 0 or joint >= 6:
            logger.error(f"Invalid joint index: {joint}")
            return
        
        try:
            if self.robot:
                # Map joint index to motor name
                motor_names = [
                    "shoulder_pan",
                    "shoulder_lift", 
                    "elbow_flex",
                    "wrist_flex",
                    "wrist_roll",
                    "gripper"
                ]
                
                motor_name = motor_names[joint]
                
                # Send command to robot
                self.robot.write("Goal_Position", {motor_name: angle})
                self.positions[joint] = angle
                
                logger.info(f"Moved {motor_name} (joint {joint}) to {angle}°")
            else:
                # Simulation mode
                self.positions[joint] = angle
                print(f"[SIM] Moving joint {joint} to {angle}°")
                
        except Exception as e:
            logger.error(f"Error moving joint {joint}: {e}")
    
    def get_joint_position(self, joint: int) -> float:
        """
        Get current position of a joint
        
        Args:
            joint: Joint index (0-5)
            
        Returns:
            Current angle in degrees
        """
        if joint < 0 or joint >= 6:
            logger.error(f"Invalid joint index: {joint}")
            return 0.0
        
        if self.robot:
            self._update_positions()
        
        return self.positions[joint]
    
    def read_all_positions(self) -> list:
        """
        Read all joint positions from robot
        
        Returns:
            List of 6 joint angles in degrees
        """
        if self.robot:
            try:
                # Read from robot
                positions_dict = self.robot.read("Present_Position")
                
                # Map motor names to joint indices
                motor_order = [
                    "shoulder_pan",      # Joint 0
                    "shoulder_lift",     # Joint 1
                    "elbow_flex",        # Joint 2
                    "wrist_flex",        # Joint 3
                    "wrist_roll",        # Joint 4
                    "gripper"            # Joint 5
                ]
                
                angles = []
                for motor_name in motor_order:
                    if motor_name in positions_dict:
                        # Get position (already in degrees from LeRobot)
                        angle = float(positions_dict[motor_name])
                        angles.append(angle)
                        logger.debug(f"{motor_name}: {angle}°")
                    else:
                        logger.warning(f"Motor {motor_name} not found in read data")
                        angles.append(0.0)
                
                # Update cache
                self.positions = angles
                
                logger.info(f"Read positions from robot: {angles}")
                return angles
                
            except Exception as e:
                logger.error(f"Error reading all positions: {e}", exc_info=True)
                return [0.0] * 6
        else:
            # Simulation mode - return cached values
            logger.info(f"[SIM] Positions: {self.positions}")
            return self.positions
    
    def disconnect(self):
        """Disconnect from robot"""
        if self.robot:
            try:
                self.robot.disconnect()
                logger.info("Robot disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting robot: {e}")


class BlocklyManager:
    """Manages Blockly programs and execution"""

    def __init__(self, robot_port: Optional[str] = None):
        self.saved_programs: Dict[str, Dict[str, Any]] = {}
        self.programs_file = Path.home() / ".lerobot_blockly_programs.json"
        self.robot_api = RobotAPI(robot_port)
        self.load_programs()
        logger.info(f"BlocklyManager initialized (robot_port: {robot_port})")

    def load_programs(self):
        """Load saved programs from disk"""
        try:
            if self.programs_file.exists():
                with open(self.programs_file, 'r') as f:
                    self.saved_programs = json.load(f)
                logger.info(f"Loaded {len(self.saved_programs)} saved programs")
        except Exception as e:
            logger.error(f"Error loading programs: {e}")
            self.saved_programs = {}

    def save_programs(self):
        """Save programs to disk"""
        try:
            with open(self.programs_file, 'w') as f:
                json.dump(self.saved_programs, f, indent=2)
            logger.info(f"Saved {len(self.saved_programs)} programs")
        except Exception as e:
            logger.error(f"Error saving programs: {e}")

    def save_program(self, name: str, workspace_json: str, python_code: str) -> bool:
        """
        Save a Blockly program
        
        Args:
            name: Program name
            workspace_json: Blockly workspace JSON representation
            python_code: Generated Python code
            
        Returns:
            True if successful
        """
        try:
            self.saved_programs[name] = {
                'workspace': workspace_json,
                'python_code': python_code,
                'timestamp': asyncio.get_event_loop().time()
            }
            self.save_programs()
            logger.info(f"Saved program: {name}")
            return True
        except Exception as e:
            logger.error(f"Error saving program {name}: {e}")
            return False

    def load_program(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Load a saved program
        
        Args:
            name: Program name
            
        Returns:
            Program dict or None
        """
        return self.saved_programs.get(name)

    def delete_program(self, name: str) -> bool:
        """
        Delete a saved program
        
        Args:
            name: Program name
            
        Returns:
            True if successful
        """
        try:
            if name in self.saved_programs:
                del self.saved_programs[name]
                self.save_programs()
                logger.info(f"Deleted program: {name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting program {name}: {e}")
            return False

    def list_programs(self) -> Dict[str, Dict[str, Any]]:
        """
        List all saved programs
        
        Returns:
            Dictionary of programs
        """
        return self.saved_programs

    async def execute_python_code(self, code: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Execute Python code safely with real robot access
        
        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds
            
        Returns:
            Execution result dict
        """
        try:
            logger.info("Executing Blockly-generated Python code")
            
            # Capture stdout
            old_stdout = sys.stdout
            sys.stdout = captured_output = io.StringIO()
            
            try:
                # Create execution environment with real robot API
                local_vars = {}
                global_vars = {
                    '__builtins__': {
                        'print': print,
                        'range': range,
                        'len': len,
                        'enumerate': enumerate,
                        'str': str,
                        'int': int,
                        'float': float,
                        'list': list,
                        'dict': dict,
                        'abs': abs,
                        'min': min,
                        'max': max,
                        'round': round,
                    },
                    'time': time,
                    'robot': self.robot_api,  # Real robot access!
                }
                
                # Execute code
                exec(code, global_vars, local_vars)
                
                # Get captured output
                output = captured_output.getvalue()
                
                return {
                    'success': True,
                    'output': output or 'Execution completed successfully',
                    'variables': {k: str(v) for k, v in local_vars.items() if not k.startswith('_')}
                }
                
            except Exception as e:
                logger.error(f"Error executing code: {e}", exc_info=True)
                output = captured_output.getvalue()
                return {
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'output': output
                }
            finally:
                sys.stdout = old_stdout
                
        except Exception as e:
            logger.error(f"Unexpected error in execute_python_code: {e}")
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }
    
    def shutdown(self):
        """Shutdown and cleanup"""
        logger.info("Shutting down BlocklyManager")
        if self.robot_api:
            self.robot_api.disconnect()

    def generate_custom_blocks(self) -> str:
        """
        Generate custom Blockly blocks definition for LeRobot
        
        Returns:
            JavaScript code for custom blocks
        """
        return """
// Custom LeRobot Blocks
Blockly.Blocks['robot_move_joint'] = {
  init: function() {
    this.appendValueInput("JOINT")
        .setCheck("Number")
        .appendField("Move joint");
    this.appendValueInput("ANGLE")
        .setCheck("Number")
        .appendField("to angle");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(230);
    this.setTooltip("Move a robot joint to specified angle");
    this.setHelpUrl("");
  }
};

Blockly.Python['robot_move_joint'] = function(block) {
  var value_joint = Blockly.Python.valueToCode(block, 'JOINT', Blockly.Python.ORDER_ATOMIC);
  var value_angle = Blockly.Python.valueToCode(block, 'ANGLE', Blockly.Python.ORDER_ATOMIC);
  var code = 'move_joint(' + value_joint + ', ' + value_angle + ')\\n';
  return code;
};

Blockly.Blocks['robot_get_position'] = {
  init: function() {
    this.appendValueInput("JOINT")
        .setCheck("Number")
        .appendField("Get position of joint");
    this.setOutput(true, "Number");
    this.setColour(230);
    this.setTooltip("Get current position of a joint");
    this.setHelpUrl("");
  }
};

Blockly.Python['robot_get_position'] = function(block) {
  var value_joint = Blockly.Python.valueToCode(block, 'JOINT', Blockly.Python.ORDER_ATOMIC);
  var code = 'get_joint_position(' + value_joint + ')';
  return [code, Blockly.Python.ORDER_FUNCTION_CALL];
};

Blockly.Blocks['robot_wait'] = {
  init: function() {
    this.appendValueInput("DURATION")
        .setCheck("Number")
        .appendField("Wait");
    this.appendDummyInput()
        .appendField("seconds");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(160);
    this.setTooltip("Wait for specified duration");
    this.setHelpUrl("");
  }
};

Blockly.Python['robot_wait'] = function(block) {
  var value_duration = Blockly.Python.valueToCode(block, 'DURATION', Blockly.Python.ORDER_ATOMIC);
  var code = 'import time\\ntime.sleep(' + value_duration + ')\\n';
  return code;
};

Blockly.Blocks['robot_gripper'] = {
  init: function() {
    this.appendDummyInput()
        .appendField("Gripper")
        .appendField(new Blockly.FieldDropdown([["Open","open"], ["Close","close"]]), "ACTION");
    this.setPreviousStatement(true, null);
    this.setNextStatement(true, null);
    this.setColour(290);
    this.setTooltip("Control gripper");
    this.setHelpUrl("");
  }
};

Blockly.Python['robot_gripper'] = function(block) {
  var dropdown_action = block.getFieldValue('ACTION');
  var code = 'gripper_' + dropdown_action + '()\\n';
  return code;
};
"""
