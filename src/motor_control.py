import time
import Jetson.GPIO as GPIO

# PWM sysfs 接口路径（取决于你的 Jetson 型号）
PWM_CHIP = "/sys/class/pwm/pwmchip0"
PWM_CHANNEL = "pwm0"



def control_direction(direction):
    """
    控制电机方向
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
def init_pwm(duty):
    """
    duty: 占空比
    """
    print(f"占空比为:{duty}")
    try:
        with open(f"{PWM_CHIP}/export", 'w') as f:
            f.write("0")
    except:
        pass  # 如果已经导出，忽略错误

    time.sleep(0.1)  # 等待设备创建

    # 设置周期和占空比
    with open(f"{PWM_CHIP}/{PWM_CHANNEL}/period", 'w') as f:
        f.write("1000000")  # 1ms -> 1kHz

    with open(f"{PWM_CHIP}/{PWM_CHANNEL}/duty_cycle", 'w') as f:
        f.write(str(int(duty)))  # 占空比 10%

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
    speed_ration : 速度比例,0-100, 停止和最高速度
    !!!注意, 在桌上测试,非上机测试最好不要超过30%
    """
    if speed_ratio > 0 and speed_ratio <= 100:
        # 计算占空比
        duty = 1000000 * speed_ratio * 0.01 
        init_pwm(duty)
    else:
        # comment: 负数或0 直接停止电机
        stop_pwm()





