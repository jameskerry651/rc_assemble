import time
try:
    import Jetson.GPIO as GPIO
except ImportError:
    print("Error: Jetson.GPIO library is not installed or unavailable.")
    GPIO = None

# PWM sysfs 接口路径（取决于你的 Jetson 型号）
PWM_CHIP = "/sys/class/pwm/pwmchip0"
PWM_CHANNEL = "pwm0"



def control_direction(direction):
    """
    pin = 33  # Pin 33 is chosen as it corresponds to GPIO13 on the Jetson board, suitable for motor control.
    :param direction: 1 或 -1
    """
    # 引脚13编号
    pin = 33
    GPIO.setmode(GPIO.BOARD)  # 设置为BOARD编号模式

    # 设置为输出模式
    GPIO.setup(pin, GPIO.OUT)
    if direction == 1:
        GPIO.output(pin, GPIO.HIGH)  # 设置 GPIO23 高电平
    elif direction == -1:
        GPIO.output(pin, GPIO.LOW)   # 设置 GPIO23 低电平

# 初始化 PWM
def init_pwm(duty, period=1000000):
    """
    duty: 占空比
    period: PWM周期，默认为1000000 (1ms -> 1kHz)
    """
    try:
        with open(f"{PWM_CHIP}/export", 'w') as f:
            f.write("0")
    except FileNotFoundError:
        pass  # 如果已经导出，忽略错误
        pass  # 如果已经导出，忽略错误

    time.sleep(0.1)  # 等待设备创建

    # 设置周期和占空比
    with open(f"{PWM_CHIP}/{PWM_CHANNEL}/period", 'w') as f:
        f.write(str(period))  # 设置周期

    with open(f"{PWM_CHIP}/{PWM_CHANNEL}/duty_cycle", 'w') as f:
        f.write(str(int(duty)))  # 设置占空比

    # 启动PWM
    with open(f"{PWM_CHIP}/{PWM_CHANNEL}/enable", 'w') as f:
        f.write("1")


def stop_pwm():
    with open(f"{PWM_CHIP}/{PWM_CHANNEL}/enable", 'w') as f:
        f.write("0")

    with open(f"{PWM_CHIP}/unexport", 'w') as f:
        f.write("0")

def set_speed(speed_ratio):
    """
    speed_ratio : 速度比例 (0-100), 表示电机速度的百分比。
                  0% 表示停止电机，100% 表示以最高速度运行电机。
    !!!注意: 在桌面测试时，建议速度比例不要超过30%，以避免损坏设备。
    """
    if speed_ratio > 0 and speed_ratio <= 100:
        # 计算占空比
        duty = 1000000 * speed_ratio * 0.01 
        init_pwm(duty)
    else:
        # comment: 负数或0 直接停止电机
        stop_pwm()





