import Jetson.GPIO as GPIO
import time
import atexit
from typing import Optional, Union

class MotorController:
    """Jetson GPIO电机控制器类"""
    def __init__(self, pwm_pin: int = 15, dir_pin: int = 22, pwm_frequency: int = 1000):
        """
        初始化电机控制器
        
        Args:
            pwm_pin (int): PWM信号引脚 (使用BOARD编号)
            dir_pin (int): 方向控制引脚 (使用BOARD编号)
            pwm_frequency (int): PWM频率 (Hz)
        """
        # 引脚配置
        self.PWM_PIN = pwm_pin
        self.DIR_PIN = dir_pin
        self.PWM_FREQUENCY = pwm_frequency
        
        # 方向常量 (如果您的H桥逻辑相反，请调整这些值)
        self.DIRECTION_FORWARD = GPIO.HIGH  # 正向
        self.DIRECTION_REVERSE = GPIO.LOW   # 反向
        
        # 内部状态
        self._pwm_motor: Optional[GPIO.PWM] = None
        self._is_initialized = False
        self._current_direction = self.DIRECTION_FORWARD
        self._current_speed = 0
        
        # 注册清理函数，确保程序退出时自动清理资源
        atexit.register(self.cleanup)
    
    def initialize(self) -> bool:
        """
        初始化GPIO引脚和PWM控制
        
        Returns:
            bool: 初始化是否成功
        """
        if self._is_initialized:
            print("电机控制引脚已经初始化")
            return True
        
        try:
            print("正在初始化GPIO...")
            GPIO.setmode(GPIO.BOARD)  # 使用物理引脚编号
            GPIO.setwarnings(False)   # 禁用非关键警告
            
            # 初始化方向控制引脚
            print(f"设置方向控制引脚 {self.DIR_PIN} 为输出模式")
            GPIO.setup(self.DIR_PIN, GPIO.OUT)
            GPIO.output(self.DIR_PIN, self._current_direction)
            
            # 初始化PWM引脚
            print(f"在引脚 {self.PWM_PIN} 上初始化PWM，频率: {self.PWM_FREQUENCY} Hz")
            print(f"注意: 引脚 {self.PWM_PIN} 将使用软件PWM")
            
            self._pwm_motor = GPIO.PWM(self.PWM_PIN, self.PWM_FREQUENCY)
            self._pwm_motor.start(0)  # 以0%占空比启动PWM (电机停止)
            
            self._is_initialized = True
            print("电机控制引脚初始化成功")
            return True
            
        except RuntimeError as e:
            print(f"错误: PWM初始化失败在引脚 {self.PWM_PIN}: {e}")
            print("请检查:")
            print("1. 是否使用 'sudo' 运行脚本")
            print(f"2. 引脚 {self.PWM_PIN} 和 {self.DIR_PIN} 是否被其他设备占用")
            self._safe_cleanup()
            return False
        except Exception as e:
            print(f"初始化过程中发生未知错误: {e}")
            self._safe_cleanup()
            return False
    
    def set_direction(self, direction: int) -> bool:
        """
        设置电机方向
        
        Args:
            direction (int): 期望的方向 (使用 DIRECTION_FORWARD 或 DIRECTION_REVERSE)
            
        Returns:
            bool: 操作是否成功
        """
        if not self._check_initialized():
            return False
        
        if direction not in [self.DIRECTION_FORWARD, self.DIRECTION_REVERSE]:
            print("错误: 无效的方向值，请使用 DIRECTION_FORWARD 或 DIRECTION_REVERSE")
            return False
        
        # 如果需要改变方向，先停止电机以避免损坏
        if direction != self._current_direction and self._current_speed > 0:
            print("方向改变时自动停止电机以确保安全")
            self._set_pwm_speed(0)
            # time.sleep(0.1)  # 短暂延迟确保电机完全停止
        
        GPIO.output(self.DIR_PIN, direction)
        # self._current_direction = direction
        
        direction_str = "正向" if direction == self.DIRECTION_FORWARD else "反向"
        print(f"电机方向设置为: {direction_str}")
        return True
    
    def set_speed(self, speed: Union[int, float]) -> bool:
        """
        设置电机速度
        
        Args:
            speed (Union[int, float]): 速度百分比 (0-100)
                                     0表示停止，100表示当前方向的最大速度
                                     
        Returns:
            bool: 操作是否成功
        """
        if not self._check_initialized():
            return False
        
        # 输入验证和限制
        speed = max(0, min(100, float(speed)))
        
        if speed != self._current_speed:
            self._set_pwm_speed(speed)
            self._current_speed = speed
            
            direction_str = "正向" if self._current_direction == self.DIRECTION_FORWARD else "反向"
            if speed == 0:
                print("电机已停止")
            else:
                print(f"电机速度设置为: {speed:.1f}% ({direction_str})")
        
        return True
    
    def stop(self) -> bool:
        """
        停止电机
        
        Returns:
            bool: 操作是否成功
        """
        return self.set_speed(0)
    
    def gradual_speed_change(self, target_speed: Union[int, float], 
                           step_size: float = 5, delay: float = 0.1) -> bool:
        """
        逐渐改变电机速度，避免突然的速度变化
        
        Args:
            target_speed (Union[int, float]): 目标速度 (0-100)
            step_size (float): 每步的速度变化量
            delay (float): 每步之间的延迟时间 (秒)
            
        Returns:
            bool: 操作是否成功
        """
        if not self._check_initialized():
            return False
        
        target_speed = max(0, min(100, float(target_speed)))
        current = self._current_speed
        
        print(f"电机速度从 {current:.1f}% 逐渐变化到 {target_speed:.1f}%")
        
        while abs(current - target_speed) > step_size:
            if current < target_speed:
                current = min(current + step_size, target_speed)
            else:
                current = max(current - step_size, target_speed)
            
            if not self.set_speed(current):
                return False
            time.sleep(delay)
        
        return self.set_speed(target_speed)
    
    def run_forward(self, speed: Union[int, float]) -> bool:
        """
        设置电机正向运行
        
        Args:
            speed (Union[int, float]): 速度百分比 (0-100)
            
        Returns:
            bool: 操作是否成功
        """
        return self.set_direction(self.DIRECTION_FORWARD) and self.set_speed(speed)
    
    def run_reverse(self, speed: Union[int, float]) -> bool:
        """
        设置电机反向运行
        
        Args:
            speed (Union[int, float]): 速度百分比 (0-100)
            
        Returns:
            bool: 操作是否成功
        """
        return self.set_direction(self.DIRECTION_REVERSE) and self.set_speed(speed)
    
    # def read_motor_dir(self) -> str:
    #     pin = 32
    #     #GPIO.setmode(GPIO.BOARD)  # 使用物理引脚编号
    #     GPIO.setup(pin, GPIO.IN)
    #     print(f"成功将 Jetson 物理引脚 {pin} 设置为输入模式。")
    #     pin_level = GPIO.input(pin)

    #     if pin_level == GPIO.HIGH:
    #         pin_state = "高电平 (1)"
    #         print(f"[{time.strftime('%H:%M:%S')}] Pin {pin} 电平: 高电平 (1)")
    #     else:
    #         pin_state = "低电平 (0)"
    #         print(f"[{time.strftime('%H:%M:%S')}] Pin {pin} 电平: 低电平 (0)")
    #     GPIO.cleanup()
    #     return pin_state

    def get_status(self) -> dict:
        """
        获取电机当前状态
        
        Returns:
            dict: 包含电机状态信息的字典
        """
        direction_str = "正向" if self._current_direction == self.DIRECTION_FORWARD else "反向"
        # 读取pin16的电平
        pin16_state = self.read_motor_dir()
        if pin16_state == GPIO.HIGH:
            direction_str += " (pin16 HIGH)"
        else:
            direction_str += " (pin16 LOW)"
        # 返回状态信息
        return {
            'initialized': self._is_initialized,
            'speed': self._current_speed,
            'direction': direction_str,
            'direction_value': self._current_direction,
            'pwm_pin': self.PWM_PIN,
            'dir_pin': self.DIR_PIN,
            'pwm_frequency': self.PWM_FREQUENCY
        }
    
    def _check_initialized(self) -> bool:
        """检查是否已初始化"""
        if not self._is_initialized:
            print("错误: 电机控制未初始化，请先调用 initialize() 方法")
            return False
        return True
    
    def _set_pwm_speed(self, speed: float):
        """设置PWM占空比"""
        if self._pwm_motor:
            self._pwm_motor.ChangeDutyCycle(speed)
    
    def _safe_cleanup(self):
        """安全清理GPIO资源"""
        try:
            if self._pwm_motor:
                self._pwm_motor.stop()
            if self._is_initialized:
                GPIO.output(self.DIR_PIN, GPIO.LOW)  # 设置安全状态
            GPIO.cleanup()
        except:
            pass  # 忽略清理过程中的错误
    
    def cleanup(self):
        """清理GPIO资源"""
        if self._is_initialized:
            print("\n正在清理GPIO资源...")
            self.stop()  # 确保电机停止
            time.sleep(0.1)
            self._safe_cleanup()
            self._is_initialized = False
            self._pwm_motor = None
            print("GPIO清理完成")


# def demo_motor_control():
#     """电机控制演示程序"""
#     print("=== Jetson GPIO 电机控制演示 ===")
    
#     # 创建电机控制器实例
#     motor = MotorController(pwm_pin=15, dir_pin=22, pwm_frequency=1000)
    
#     # 显示配置信息
#     status = motor.get_status()
#     print(f"PWM引脚 (BOARD): {status['pwm_pin']}")
#     print(f"方向控制引脚 (BOARD): {status['dir_pin']}")
#     print(f"PWM频率: {status['pwm_frequency']} Hz")
#     print("确保您的电机驱动器连接正确!")
#     print("按 Ctrl+C 退出并清理资源")
    
#     # 初始化电机控制
#     if not motor.initialize():
#         print("由于初始化失败而退出")
#         return
    
#     try:
#         print("\n=== 电机测试序列 ===")
        
#         # 测试正向运行
#         print("\n1. 正向运行测试")
#         motor.run_forward(0)
#         time.sleep(0.5)
        
#         print("逐渐加速...")
#         for speed in [30, 11, 15, 10]:
#             motor.gradual_speed_change(speed, step_size=10, delay=0.1)
#             time.sleep(2)
        
#         motor.stop()
#         time.sleep(1)
        
#         # 测试反向运行
#         print("\n2. 反向运行测试")  
#         motor.run_reverse(0)
#         time.sleep(0.5)
        
#         print("逐渐加速...")
#         for speed in [30, 11, 15, 10]:
#             motor.gradual_speed_change(speed, step_size=10, delay=0.1)
#             time.sleep(2)
        
#         motor.stop()
#         time.sleep(1)
        
#         # 测试方向快速切换
#         print("\n3. 方向切换测试")
#         motor.run_forward(30)
#         time.sleep(2)
#         motor.run_reverse(30)  # 自动先停止再改变方向
#         time.sleep(2)
#         motor.stop()
        
#         print("\n测试序列完成")
        
#         # 显示最终状态
#         print(f"\n最终状态: {motor.get_status()}")
        
#     except KeyboardInterrupt:
#         print("\n用户中断，正在停止电机并清理资源")
#     except Exception as e:
#         print(f"\n发生错误: {e}")
#         import traceback
#         traceback.print_exc()
#     finally:
#         motor.cleanup()


# if __name__ == "__main__":
#     demo_motor_control()