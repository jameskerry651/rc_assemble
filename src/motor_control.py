import time

# PWM sysfs 接口路径（取决于你的 Jetson 型号）
PWM_CHIP = "/sys/class/pwm/pwmchip0"
PWM_CHANNEL = "pwm0"

# 初始化 PWM
def init_pwm():
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
        f.write("500000")  # 占空比 50%

    # 启动PWM
    with open(f"{PWM_CHIP}/{PWM_CHANNEL}/enable", 'w') as f:
        f.write("1")

def stop_pwm():
    with open(f"{PWM_CHIP}/{PWM_CHANNEL}/enable", 'w') as f:
        f.write("0")

    with open(f"{PWM_CHIP}/unexport", 'w') as f:
        f.write("0")

# 主程序
try:
    init_pwm()
    print("PWM 输出中... 持续 10 秒")
    time.sleep(10)
finally:
    stop_pwm()
    print("PWM 停止")
