import pygame
import sys
import time

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

def init_joystick():
    """初始化 Pygame 和手柄"""
    pygame.init()
    pygame.joystick.init()

    joystick_count = pygame.joystick.get_count()
    if joystick_count == 0:
        print("未检测到手柄，请检查是否已插入并且打开。")
        pygame.quit()
        sys.exit(1)

    joystick = pygame.joystick.Joystick(0) # 使用第一个检测到的手柄
    joystick.init() # 初始化手柄对象

    print(f"已找到手柄：{joystick.get_name()}")
    print(f"  按钮数量：{joystick.get_numbuttons()}")
    print(f"  轴数量：{joystick.get_numaxes()}")
    print(f"  方向键(Hats)数量：{joystick.get_numhats()}")
    
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


def main_loop(joystick: pygame.joystick.Joystick):

    print(f"\n开始监听左摇杆横向(轴 {LEFT_STICK_X_AXIS})和右摇杆纵向(轴 {RIGHT_STICK_Y_AXIS})的值变化。")
    print(f"左摇杆X控制舵机角度: [{SERVO_MIN_ANGLE}° - {SERVO_MAX_ANGLE}°]，中心 {SERVO_CENTER_ANGLE}°")
    print("按 Ctrl+C 退出程序。")
    
    running = True
    last_servo_angle_sent = -1 # 用于减少重复发送相同的舵机角度

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
                        state_desc = "居中"
                        if value < -DEADZONE_THRESHOLD: # value < 0 表示“向上”
                            state_desc = f"向上 {value:+.3f}"
                        elif value > DEADZONE_THRESHOLD: # value > 0 表示“向下”
                            state_desc = f"向下 {value:+.3f}"
                        else:
                            # 在死区内，但为了清晰，即使在此处不执行任何操作，也打印状态
                            pass # state_desc 已经是 "居中"
                        
                        # 只有当状态有意义时才打印（不在死区内或刚进入死区）
                        if abs(value) >= DEADZONE_THRESHOLD or state_desc == "居中": # 简化逻辑，总是打印
                             print(f"[右摇杆 Y (轴 {axis_index})] 值: {value:+.3f} -> 状态: {state_desc}")
            
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