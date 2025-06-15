"""
servo_pwm.py

在 Jetson AGX Orin 的物理引脚 13（BOARD 编号）上输出 50Hz PWM 控制舵机转动。
提供一个 set_servo_angle(angle) 函数，angle 范围 0-180 度。

注意：
    - 确保物理引脚 13 已在设备树/Jetson-IO 中复用为 PWM 模式。
    - 典型舵机信号：50Hz 周期 (20ms)，脉宽 0.5ms (~2.5% 占空比) 对应 0°，
      脉宽 2.5ms (~12.5% 占空比) 对应 180°；中位 1.5ms (~7.5% 占空比) 对应 90°。
"""

import Jetson.GPIO as GPIO
import time

# ——————————————————————————————————————————————————————————————————————————————————
# 配置参数
PWM_PIN_BOARD = 33      # 物理引脚编号（BOARD 模式）
PWM_FREQ_HZ   = 50      # 舵机常用控制频率：50Hz
ANGLE_MIN     = 0       # 舵机最小角度
ANGLE_MAX     = 180     # 舵机最大角度
DUTY_MIN      = 2.5     # 0° 时的占空比（%）
DUTY_MAX      = 12.5    # 180° 时的占空比（%）
# ——————————————————————————————————————————————————————————————————————————————————


def angle_to_duty_cycle(angle: float) -> float:
    """
    将舵机角度 (0~180) 映射到占空比 (DUTY_MIN~DUTY_MAX)。
    参数:
        angle: float，舵机目标角度，范围 [0, 180]
    返回:
        duty: float，对应的 PWM 占空比（单位 %）
    """
    if angle < ANGLE_MIN or angle > ANGLE_MAX:
        raise ValueError(f"angle 必须在 [{ANGLE_MIN}, {ANGLE_MAX}] 之间，收到: {angle}")
    # 线性映射：angle=0 -> duty=DUTY_MIN，angle=180 -> duty=DUTY_MAX
    duty_range = DUTY_MAX - DUTY_MIN
    duty = DUTY_MIN + (duty_range) * (angle - ANGLE_MIN) / (ANGLE_MAX - ANGLE_MIN)
    return duty


def initialize_pwm(pin_board: int, freq_hz: int) -> GPIO.PWM:
    """
    初始化 Jetson.GPIO 的 PWM 输出，返回 PWM 对象。
    参数:
        pin_board: int，物理 BOARD 编号（如 13）
        freq_hz: int，PWM 频率 (Hz)
    返回:
        pwm: GPIO.PWM，已经 start(0) 但尚未设定占空比
    """
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(pin_board, GPIO.OUT, initial=GPIO.LOW)
    pwm = GPIO.PWM(pin_board, freq_hz)
    pwm.start(0.0)   # 先启用 PWM，初始占空比 0%
    return pwm


def cleanup_pwm(pwm: GPIO.PWM):
    """
    停止 PWM 并清理 GPIO 设置，程序退出时可调用。
    参数:
        pwm: GPIO.PWM，待停止的 PWM 对象
    """
    pwm.stop()
    GPIO.cleanup()


_pwm_servo = None

def set_servo_angle(angle: float):
    """
    将舵机转到指定角度（0~180）。
    首次调用时，会自动初始化 PWM 输出；随后调用只改变占空比。
    参数:
        angle: float，舵机目标角度，范围 [0, 180]
    """
    global _pwm_servo
    # 第一次调用时，初始化 PWM
    if _pwm_servo is None:
        # 假设 initialize_pwm 和 angle_to_duty_cycle 是你已有的函数
        # from your_pwm_setup_module import initialize_pwm, PWM_PIN_BOARD, PWM_FREQ_HZ 
        # from your_angle_converter import angle_to_duty_cycle
        
        # 示例占位：你需要用实际的函数替换
        # _pwm_servo = initialize_pwm(PWM_PIN_BOARD, PWM_FREQ_HZ)
        print("PWM 首次初始化 (模拟)") # 替换为实际的初始化
        _pwm_servo = initialize_pwm(PWM_PIN_BOARD, PWM_FREQ_HZ)
        
        # 这里的短暂 sleep 是为了确保 PWM 初始化后稳定，可以保留或调整
        time.sleep(0.1) 

    # 将角度转换为占空比
    duty = angle_to_duty_cycle(angle) # 确保你有这个函数
    # 对于50Hz，0度约2.5% (0.5ms)，90度约7.5% (1.5ms)，180度约12.5% (2.5ms)
    

    if _pwm_servo: # 确保 _pwm_servo 已被初始化
        _pwm_servo.ChangeDutyCycle(duty)
        print(f"(模拟) PWM ChangeDutyCycle to {duty:.2f} for angle {angle:.1f}°") # 替换为实际的调用
    else:
        print("错误: _pwm_servo 未初始化！")



if __name__ == "__main__":
    try:
        set_servo_angle(45)    # 设置舵机到 45°
        time.sleep(0.2)  # 等待舵机到位

        print("测试结束，退出并清理 GPIO。")
    except KeyboardInterrupt:
        print("用户中断，退出并清理 GPIO。")
    finally:
        if _pwm_servo is not None:
            cleanup_pwm(_pwm_servo)
