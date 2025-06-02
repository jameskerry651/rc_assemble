import pygame
import sys
import time
import math

# --- 常量定义 ---
# 手柄轴配置 (这些值可能因手柄型号而异)
LEFT_STICK_X_AXIS = 0  # 左摇杆横向轴
# LEFT_STICK_Y_AXIS = 1 # 左摇杆纵向轴 (未使用)
# RIGHT_STICK_X_AXIS = 2 # 右摇杆横向轴 (未使用)
RIGHT_STICK_Y_AXIS = 3 # 右摇杆纵向轴

# 摇杆死区：摇杆在这个范围内的微小抖动将被忽略
DEADZONE_THRESHOLD = 0.05 # 

# 舵机角度配置
SERVO_MIN_ANGLE = 0
SERVO_CENTER_ANGLE = 90
SERVO_MAX_ANGLE = 180

# 主循环延迟
LOOP_DELAY_S = 0.02  # 循环间的等待时间（秒），例如 0.02s = 20ms = 50Hz

# --- 舵机控制模块导入与模拟 ---
try:
    from servo_pwm import set_servo_angle
    print("servo_pwm 模块已成功导入。")
except ImportError:
    print("警告：servo_pwm 模块未找到。舵机控制将不可用。")
    exit(-1)

# --- 电机控制模块导入 ---
try:
    from motor_contro_agx import MotorController
    print("motor_contro_agx 模块已成功导入。")
except ImportError:
    print("警告：motor_contro_agx 模块未找到。电机控制将不可用。")
    exit(-1)

def init_joystick():
    """初始化 Pygame 和手柄"""
    pygame.init()
    pygame.joystick.init()

    joystick_count = pygame.joystick.get_count()
    if joystick_count == 0:
        while True:
            print("未检测到手柄，请检查是否已插入并且打开。")
            print("请插入手柄后按任意键继续...")
            print("请检查sudo 权限是否正确，确保手柄驱动已安装。")
            time.sleep(2)  # 等待一段时间，避免过于频繁的检测
            if pygame.joystick.get_count() > 0:
                break

    joystick = pygame.joystick.Joystick(0) # 使用第一个检测到的手柄
    joystick.init() # 初始化手柄对象

    print(f"已找到手柄：{joystick.get_name()}")
    
    if joystick.get_numaxes() < max(LEFT_STICK_X_AXIS, RIGHT_STICK_Y_AXIS) + 1:
        print(f"错误：手柄轴数量不足以支持所需的轴 (需要至少 {max(LEFT_STICK_X_AXIS, RIGHT_STICK_Y_AXIS) + 1} 个轴)。")
        joystick.quit()
        pygame.joystick.quit()
        pygame.quit()
        sys.exit(1)
        
    return joystick


def calculate_servo_angle(joystick_value: float,
                          deadzone: float,
                          min_angle: float, center_angle: float, max_angle: float) -> float:
    """
    将摇杆轴值映射到舵机角度。
    摇杆值: -1.0 (全左/上) 到 +1.0 (全右/下)
    舵机角度: min_angle, center_angle, max_angle (例如 0, 90, 180)
    """
    if abs(joystick_value) < deadzone:
        return center_angle
    
    # joystick_value < 0 (例如: 左摇杆向左)
    # 摇杆值范围: [-1.0, -deadzone]
    # 舵机角度应映射到: [max_angle, center_angle] (例如 180° 到 90°)
    if joystick_value < -deadzone:
        # 将 joystick_value 从 [-1.0, -deadzone] 归一化到 [1.0, 0.0]
        effective_value = (abs(joystick_value) - deadzone) / (1.0 - deadzone)
        angle = center_angle + effective_value * (max_angle - center_angle)
       

    # joystick_value > 0 (例如: 左摇杆向右)
    # 摇杆值范围: [deadzone, 1.0]
    # 舵机角度应映射到: [center_angle, min_angle] (例如 90° 到 0°)
    elif joystick_value > deadzone:
        # 将 joystick_value 从 [deadzone, 1.0] 归一化到 [0.0, 1.0]
        effective_value = (joystick_value - deadzone) / (1.0 - deadzone)
        angle = center_angle - effective_value * (center_angle - min_angle)
       
    else: # 理论上不会到这里，因为上面已经处理了 abs(value) < deadzone
        angle = center_angle
        
    # 限制舵机角度在 min_angle 和 max_angle 之间
    return max(min_angle, min(max_angle, angle))





def calculate_motor_speed(joystick_value: float, 
                         deadzone: float = 0.1,
                         center_speed: float = 0.0, 
                         min_speed: float = 0.0, 
                         max_speed: float = 30.0) -> float:
    """
    将摇杆值映射为电机速度和方向
    
    Args:
        joystick_value (float): 摇杆输入值，范围通常为 -1.0 到 1.0
                               正值表示向前，负值表示向后
        deadzone (float): 死区范围，摇杆在此范围内视为中心位置 (默认: 0.1)
        min_speed (float): 最小运行速度，超出死区后的最小速度 (默认: 20.0)
        center_speed (float): 中心速度，通常为0表示停止 (默认: 0.0)
        max_speed (float): 最大运行速度 (默认: 100.0)
        
    Returns:
        float: 映射后的电机速度
               正值表示正向运行，负值表示反向运行
               0表示停止

    """
    
    # 参数验证
    if not isinstance(joystick_value, (int, float)):
        raise TypeError("摇杆值必须是数字类型")
    
    if deadzone < 0 or deadzone >= 1:
        raise ValueError("死区值必须在 0 到 1 之间")
    
    if min_speed < 0 or max_speed <= min_speed:
        raise ValueError("速度参数无效: max_speed > min_speed >= 0")
    
    # 限制摇杆输入值范围到 [-1, 1]
    joystick_value = max(-1.0, min(1.0, float(joystick_value)))
    
    # 获取摇杆值的绝对值和方向
    abs_value = abs(joystick_value)
    direction = 1 if joystick_value >= 0 else -1
    
    # 死区处理：如果摇杆值在死区范围内，返回中心速度
    if abs_value <= deadzone:
        return center_speed
    
    # 计算有效摇杆范围 (去除死区后的范围)
    effective_range = 1.0 - deadzone
    effective_value = (abs_value - deadzone) / effective_range
    
    # 将有效值映射到速度范围 [min_speed, max_speed]
    speed_range = max_speed - min_speed
    mapped_speed = min_speed + (effective_value * speed_range)
    
    # 应用方向并返回结果
    return direction * mapped_speed


def main_loop(joystick: pygame.joystick.Joystick):

    print(f"\n开始监听左摇杆横向(轴 {LEFT_STICK_X_AXIS})和右摇杆纵向(轴 {RIGHT_STICK_Y_AXIS})的值变化。")
    print(f"左摇杆X控制舵机角度: [{SERVO_MIN_ANGLE}° - {SERVO_MAX_ANGLE}°]，中心 {SERVO_CENTER_ANGLE}°")
    print("按 Ctrl+C 退出程序。")
    
     # 创建电机控制器实例
    motor = MotorController(pwm_pin=15, dir_pin=13, pwm_frequency=1000)
  
     # 初始化电机控制
    if not motor.initialize():
        print("由于初始化失败而退出")
        exit(-1)

    running = True
    last_servo_angle_sent = -1 # 用于减少重复发送相同的舵机角度
    last_motor_speed = 0 # 用于跟踪上次的电机速度

    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.JOYAXISMOTION:
                    axis_index = event.axis
                    value = event.value  # 轴值范围 [-1.0, +1.0]

                    # --- 左摇杆横向 (控制舵机) ---
                    if axis_index == LEFT_STICK_X_AXIS:
                        
                        servo_angle_float = calculate_servo_angle(
                            value, 
                            DEADZONE_THRESHOLD,
                            SERVO_MIN_ANGLE, 
                            SERVO_CENTER_ANGLE, 
                            SERVO_MAX_ANGLE
                        )
                        servo_angle_int = int(round(servo_angle_float))

                        # 仅当角度变化时才发送指令并打印，减少通讯和日志噪音
                        if servo_angle_int != last_servo_angle_sent:
                            set_servo_angle(servo_angle_int)
                            last_servo_angle_sent = servo_angle_int
                            
                            state_desc = "居中"
                            if value < -DEADZONE_THRESHOLD:
                                state_desc = f"向左 {value:+.3f}"
                            elif value > DEADZONE_THRESHOLD:
                                state_desc = f"向右 {value:+.3f}"
                            
                            print(f"[左摇杆 X (轴 {axis_index})] 值: {value:+.3f} -> 舵机角度: {servo_angle_int}° ({state_desc})")

                    # --- 右摇杆纵向 (仅显示信息) ---
                    elif axis_index == RIGHT_STICK_Y_AXIS:
                        motor_speed = int(calculate_motor_speed(value))
                        print(f"[右摇杆 Y (轴 {axis_index})] 值: {value:+.3f} -> 电机速度: {motor_speed:+.2f} (正值表示向前，负值表示向后)")
                        # 仅当电机速度变化时才发送指令并打印，减少通讯和日志噪音
                        if motor_speed != last_motor_speed:

                            last_motor_speed = motor_speed
                            if value < -DEADZONE_THRESHOLD: # value < 0 表示“向上”
                                motor.run_forward(abs(motor_speed))
                                state_desc = f"向上 {value:+.3f}"
                            elif value > DEADZONE_THRESHOLD: # value > 0 表示“向下”
                                motor.run_reverse(abs(motor_speed))
                                state_desc = f"向下 {value:+.3f}"
                            else:
                                # 在死区内
                                motor.stop() # 停止电机
                                pass # state_desc 已经是 "居中"
            
            if not running: # 如果内部循环因为 pygame.QUIT 而中断
                break
                
            time.sleep(LOOP_DELAY_S) # 等待一小段时间，降低CPU使用率

    except KeyboardInterrupt:
        print("\n用户手动终止，退出程序。")
    finally:
        if joystick:
            joystick.quit()
        pygame.joystick.quit()
        pygame.quit()
        print("Pygame 已安全退出。")

if __name__ == "__main__":
    joystick_instance = init_joystick()
    if joystick_instance: # 确保手柄成功初始化
        main_loop(joystick_instance)