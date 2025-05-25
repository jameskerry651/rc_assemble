from motor_control import *

# 主程序
try:
    control_direction(1)  # 设置方向为正转
    print("电机正转中... 持续 10 秒")
    set_speed(30)
    print("PWM 输出中... 持续 10 秒")
    time.sleep(5)
finally:
    stop_pwm()
    print("PWM 停止")
