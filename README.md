# rc_assemble

本仓库致力于构建一个基于自组装RC遥控车硬件的智能车平台，包含完整的软件代码与硬件方案。鉴于RC领域成熟的车架、高性能电调及1:10的真实复刻设计带来的丰富配件生态，其机械基础远优于传统智能车方案。

然而，现有RC系统通常缺乏速度反馈机制，且对高级传感器（如相机、激光雷达、IMU）的集成支持不足。本项目旨在解决这些痛点，通过提供一套可接入上位机的解决方案，使RC车辆能够加载自定义控制程序，从而成为教学与智能车竞赛的理想开发平台。



## 在jetson nano上配置电机PWM
打开终端，运行：


`` sudo /opt/nvidia/jetson-io/jetson-io.py ``

进入后：

选择：Configure Jetson 40-pin Header
然后选择：PWM1 或 PWM2
保存并重启 Jetson

重启后，运行：

`` ls /sys/class/pwm/ ``

进入目录

`` cd /sys/class/pwm/pwmchip0``

导出 PWM 通道（一般是 0）：

`` echo 0 | sudo tee export ``


## NVIDIA Jetson Orin Nano 引脚配置
为了给RC车输出两路pwm信号，需要占用至少2个pwm口，以下为Jetson Orin Nano的引脚配置

Pin 15 : 给无刷电机输出pwm脉冲
Pin 33 ：给舵机输出pwm脉冲

Pin 13 : 给无刷电机输出方向信号

