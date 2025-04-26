#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Nintendo Switch 数据收集脚本
用于定时任务自动收集游戏数据
"""

import os
import sys
import time
import logging
from datetime import datetime
import subprocess

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("daily_collect.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("daily_collect")

def main():
    """主函数，运行数据收集过程"""
    try:
        logger.info("开始执行每日数据收集")
        
        # 获取脚本所在目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # 运行数据收集脚本
        logger.info("运行 get_switch_data.py")
        result = subprocess.run([sys.executable, "get_switch_data.py"], 
                               capture_output=True, 
                               text=True)
        
        # 检查脚本运行结果
        if result.returncode == 0:
            logger.info("数据收集完成")
            logger.debug(f"输出: {result.stdout}")
            
            # 可选：启动或重启Web服务器
            # 如果你已经设置了系统服务来运行服务器，这步可以省略
            try:
                # 检查服务器是否已在运行
                server_pid_file = "server.pid"
                if os.path.exists(server_pid_file):
                    with open(server_pid_file, "r") as f:
                        pid = int(f.read().strip())
                    
                    # 尝试终止现有进程
                    try:
                        os.kill(pid, 15)  # SIGTERM
                        logger.info(f"已终止旧的服务器进程 (PID: {pid})")
                        time.sleep(2)  # 给进程一些时间来关闭
                    except ProcessLookupError:
                        logger.info("旧的服务器进程已不存在")
                
                # 启动新的服务器进程
                server_process = subprocess.Popen(
                    [sys.executable, "server.py"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # 保存新的PID
                with open(server_pid_file, "w") as f:
                    f.write(str(server_process.pid))
                
                logger.info(f"Web服务器已启动 (PID: {server_process.pid})")
            except Exception as e:
                logger.error(f"启动Web服务器时出错: {str(e)}")
        else:
            logger.error("数据收集失败")
            logger.error(f"错误: {result.stderr}")
        
        logger.info("每日数据收集任务完成")
    except Exception as e:
        logger.error(f"执行过程中出现错误: {str(e)}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 