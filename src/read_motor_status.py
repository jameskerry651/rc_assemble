#!/usr/bin/env python3
"""
Jetson AGX Orin 电机转速脉冲测量程序
专门优化用于电机编码器信号处理
"""

import time
import threading
from collections import deque
import statistics
import numpy as np
import json
from datetime import datetime

class MotorSpeedReader:
    def __init__(self, pin, encoder_ppr=1000, method='jetson_gpio', rpm_range=(0, 6000)):
        """
        电机转速读取器
        
        Args:
            pin: GPIO引脚号
            encoder_ppr: 编码器每转脉冲数 (Pulses Per Revolution)
            method: GPIO库类型
            rpm_range: 转速范围 (min_rpm, max_rpm)
        """
        self.pin = pin
        self.encoder_ppr = encoder_ppr
        self.method = method
        self.min_rpm, self.max_rpm = rpm_range
        
        # 计算脉冲频率范围
        self.min_freq = (self.min_rpm * encoder_ppr) / 60  # Hz
        self.max_freq = (self.max_rpm * encoder_ppr) / 60  # Hz
        
        # 存储脉冲间隔
        self.pulse_intervals = deque(maxlen=50)
        self.rpm_history = deque(maxlen=100)
        
        self.last_pulse_time = 0
        self.current_rpm = 0.0
        self.is_running = False
        self.lock = threading.Lock()
        
        # 动态调整的滤波参数
        self.min_interval = 1.0 / self.max_freq if self.max_freq > 0 else 0.0001  # 最小间隔
        self.max_interval = 1.0 / max(self.min_freq, 1) if self.min_freq > 0 else 1.0  # 最大间隔
        
        # 低速检测参数
        self.low_speed_threshold = 100  # RPM
        self.stopped_timeout = 2.0  # 秒，超过此时间无脉冲认为停止
        
        print(f"电机转速测量初始化:")
        print(f"- 编码器PPR: {encoder_ppr}")
        print(f"- 转速范围: {self.min_rpm}-{self.max_rpm} RPM")
        print(f"- 脉冲频率范围: {self.min_freq:.1f}-{self.max_freq:.1f} Hz")
        
        self._init_gpio()
    
    def _init_gpio(self):
        """初始化GPIO"""
        try:
            import Jetson.GPIO as GPIO
            self.GPIO = GPIO
            
            GPIO.setmode(GPIO.BOARD)
            GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            
            print(f"GPIO初始化完成，引脚: {self.pin}")
            
        except ImportError:
            raise ImportError("请安装Jetson.GPIO: sudo pip3 install Jetson.GPIO")
    
    def _pulse_callback(self, channel):
        """脉冲中断回调 - 专门优化用于电机编码器"""
        current_time = time.perf_counter()
        
        with self.lock:
            if self.last_pulse_time > 0:
                interval = current_time - self.last_pulse_time
                
                # 验证间隔是否在合理范围内
                if self.min_interval <= interval <= self.max_interval:
                    self.pulse_intervals.append(interval)
                elif interval > self.max_interval:
                    # 可能是低速或停止状态
                    if interval < self.stopped_timeout:
                        self.pulse_intervals.append(interval)
            
            self.last_pulse_time = current_time
    
    def start_reading(self):
        """开始转速测量"""
        self.is_running = True
        
        # 根据最高转速计算防抖时间
        bounce_time = max(1, int(30000 / self.max_freq))  # 动态防抖
        bounce_time = min(bounce_time, 10)  # 限制最大10ms
        
        self.GPIO.add_event_detect(
            self.pin,
            self.GPIO.RISING,
            callback=self._pulse_callback,
            bouncetime=bounce_time
        )
        
        print(f"开始转速测量，防抖时间: {bounce_time}ms")
        
        # 启动计算线程
        self.calc_thread = threading.Thread(target=self._calculate_rpm)
        self.calc_thread.daemon = True
        self.calc_thread.start()
        
        # 启动低速监控线程
        self.monitor_thread = threading.Thread(target=self._monitor_stopped)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def _calculate_rpm(self):
        """计算转速"""
        while self.is_running:
            time.sleep(0.1)  # 100ms更新频率
            
            with self.lock:
                if len(self.pulse_intervals) >= 3:
                    intervals = list(self.pulse_intervals)
                    
                    # 根据转速范围选择不同的计算策略
                    if len(intervals) >= 10:
                        # 高速时使用更多样本，提高精度
                        recent_intervals = intervals[-10:]
                    else:
                        recent_intervals = intervals
                    
                    # 异常值过滤
                    if len(recent_intervals) >= 5:
                        # 使用四分位数方法过滤异常值
                        sorted_intervals = sorted(recent_intervals)
                        q1 = np.percentile(sorted_intervals, 25)
                        q3 = np.percentile(sorted_intervals, 75)
                        iqr = q3 - q1
                        
                        filtered_intervals = [x for x in recent_intervals 
                                            if q1 - 1.5*iqr <= x <= q3 + 1.5*iqr]
                        
                        if filtered_intervals:
                            recent_intervals = filtered_intervals
                    
                    # 计算转速
                    if recent_intervals:
                        # 使用中位数间隔计算，更稳定
                        median_interval = statistics.median(recent_intervals)
                        frequency = 1.0 / median_interval
                        rpm = (frequency * 60) / self.encoder_ppr
                        
                        # 转速范围检查
                        if self.min_rpm <= rpm <= self.max_rpm:
                            self.current_rpm = rpm
                            self.rpm_history.append(rpm)
                        else:
                            # 超出范围，可能是噪声，保持上一个值
                            pass
                else:
                    # 样本不足，检查是否是低速状态
                    if len(self.pulse_intervals) == 0:
                        current_time = time.perf_counter()
                        if (current_time - self.last_pulse_time) > self.stopped_timeout:
                            self.current_rpm = 0.0
    
    def _monitor_stopped(self):
        """监控电机停止状态"""
        while self.is_running:
            time.sleep(0.5)
            
            current_time = time.perf_counter()
            if self.last_pulse_time > 0:
                time_since_last_pulse = current_time - self.last_pulse_time
                
                # 如果长时间无脉冲，认为电机已停止
                if time_since_last_pulse > self.stopped_timeout:
                    with self.lock:
                        self.current_rpm = 0.0
                        self.pulse_intervals.clear()
    
    def get_rpm(self):
        """获取当前转速"""
        return self.current_rpm
    
    def get_detailed_stats(self):
        """获取详细转速统计"""
        with self.lock:
            if len(self.rpm_history) < 3:
                return {
                    'current_rpm': self.current_rpm,
                    'samples': len(self.rpm_history),
                    'status': 'Initializing' if self.current_rpm > 0 else 'Stopped'
                }
            
            recent_rpms = list(self.rpm_history)[-20:]  # 最近20个读数
            
            return {
                'current_rpm': self.current_rpm,
                'avg_rpm': statistics.mean(recent_rpms),
                'median_rpm': statistics.median(recent_rpms),
                'std_rpm': statistics.stdev(recent_rpms) if len(recent_rpms) > 1 else 0,
                'min_rpm': min(recent_rpms),
                'max_rpm': max(recent_rpms),
                'samples': len(recent_rpms),
                'pulse_frequency': (self.current_rpm * self.encoder_ppr) / 60,
                'stability_percent': self._calculate_stability(recent_rpms),
                'status': self._get_motor_status()
            }
    
    def _calculate_stability(self, rpm_values):
        """计算转速稳定性百分比"""
        if len(rpm_values) < 5:
            return 0.0
        
        mean_rpm = statistics.mean(rpm_values)
        std_rpm = statistics.stdev(rpm_values)
        
        if mean_rpm > 0:
            cv = (std_rpm / mean_rpm) * 100
            stability = max(0, 100 - cv)  # 变异系数越小，稳定性越高
            return min(100, stability)
        
        return 0.0
    
    def _get_motor_status(self):
        """获取电机状态"""
        if self.current_rpm == 0:
            return "Stopped"
        elif self.current_rpm < self.low_speed_threshold:
            return "Low Speed"
        elif self.current_rpm > self.max_rpm * 0.9:
            return "High Speed"
        else:
            return "Normal"
    
    def calibrate_encoder_ppr(self, known_rpm, duration=10):
        """编码器PPR校准功能"""
        print(f"开始PPR校准，请确保电机以 {known_rpm} RPM 稳定运行...")
        print(f"校准时间: {duration} 秒")
        
        pulse_count = 0
        start_time = time.perf_counter()
        
        def calibration_callback(channel):
            nonlocal pulse_count
            pulse_count += 1
        
        # 临时设置校准回调
        self.GPIO.remove_event_detect(self.pin)
        self.GPIO.add_event_detect(self.pin, self.GPIO.RISING, 
                                 callback=calibration_callback, bouncetime=1)
        
        time.sleep(duration)
        
        # 恢复正常回调
        self.GPIO.remove_event_detect(self.pin)
        self.GPIO.add_event_detect(self.pin, self.GPIO.RISING, 
                                 callback=self._pulse_callback, bouncetime=1)
        
        actual_time = time.perf_counter() - start_time
        calculated_ppr = (pulse_count * 60) / (known_rpm * actual_time)
        
        print(f"校准结果:")
        print(f"- 检测到脉冲数: {pulse_count}")
        print(f"- 实际测量时间: {actual_time:.2f} 秒")
        print(f"- 计算得到PPR: {calculated_ppr:.1f}")
        print(f"- 当前设置PPR: {self.encoder_ppr}")
        
        return calculated_ppr
    
    def save_data_log(self, filename=None):
        """保存测量数据日志"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"motor_speed_log_{timestamp}.json"
        
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'encoder_ppr': self.encoder_ppr,
            'rpm_range': [self.min_rpm, self.max_rpm],
            'rpm_history': list(self.rpm_history),
            'current_stats': self.get_detailed_stats()
        }
        
        with open(filename, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        print(f"数据已保存到: {filename}")
    
    def stop_reading(self):
        """停止测量"""
        self.is_running = False
        self.GPIO.remove_event_detect(self.pin)
        self.GPIO.cleanup()
        print("转速测量已停止")

class RPMFilter:
    """转速滤波器 - 专门用于电机转速平滑"""
    
    def __init__(self, alpha=0.1, deadband=5):
        """
        Args:
            alpha: 低通滤波系数 (0-1, 越小越平滑)
            deadband: 死区范围 (RPM)，小于此变化将被忽略
        """
        self.alpha = alpha
        self.deadband = deadband
        self.filtered_rpm = 0.0
        self.last_raw_rpm = 0.0
    
    def filter(self, raw_rpm):
        """滤波处理"""
        # 死区滤波
        if abs(raw_rpm - self.last_raw_rpm) < self.deadband:
            raw_rpm = self.last_raw_rpm
        
        # 低通滤波
        if self.filtered_rpm == 0:
            self.filtered_rpm = raw_rpm
        else:
            self.filtered_rpm = self.alpha * raw_rpm + (1 - self.alpha) * self.filtered_rpm
        
        self.last_raw_rpm = raw_rpm
        return self.filtered_rpm

def main():
    """主函数"""
    # 配置参数 - 根据你的电机和编码器修改
    GPIO_PIN = 7           # GPIO引脚
    ENCODER_PPR = 1000      # 编码器每转脉冲数
    RPM_RANGE = (0, 3000)   # 转速范围
    
    try:
        print("=== 电机转速测量系统 ===")
        reader = MotorSpeedReader(
            pin=GPIO_PIN,
            encoder_ppr=ENCODER_PPR,
            rpm_range=RPM_RANGE
        )
        
        # 创建滤波器
        rpm_filter = RPMFilter(alpha=0.15, deadband=10)
        
        reader.start_reading()
        
        print("\n转速测量已开始，按Ctrl+C停止")
        print("命令：'c' - 校准PPR, 's' - 保存数据, 'q' - 退出")
        print("-" * 50)
        
        try:
            while True:
                time.sleep(1)
                
                stats = reader.get_detailed_stats()
                
                if stats['samples'] >= 3:
                    # 应用滤波
                    filtered_rpm = rpm_filter.filter(stats['current_rpm'])
                    
                    print(f"\n当前转速: {filtered_rpm:.1f} RPM")
                    print(f"原始转速: {stats['current_rpm']:.1f} RPM")
                    print(f"平均转速: {stats['avg_rpm']:.1f} RPM")
                    print(f"转速范围: {stats['min_rpm']:.1f} - {stats['max_rpm']:.1f} RPM")
                    print(f"标准差: {stats['std_rpm']:.1f} RPM")
                    print(f"脉冲频率: {stats['pulse_frequency']:.1f} Hz")
                    print(f"稳定性: {stats['stability_percent']:.1f}%")
                    print(f"电机状态: {stats['status']}")
                    print(f"样本数: {stats['samples']}")
                else:
                    print(f"等待稳定... 当前转速: {stats['current_rpm']:.1f} RPM")
                
                print("-" * 50)
                
        except KeyboardInterrupt:
            print("\n正在停止测量...")
            
            # 询问是否保存数据
            try:
                save = input("是否保存测量数据? (y/N): ").lower().strip()
                if save == 'y':
                    reader.save_data_log()
            except:
                pass
    
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if 'reader' in locals():
            reader.stop_reading()

if __name__ == "__main__":
    main()