# run.py (Entry point for the Flask application)

import os
from dotenv import load_dotenv # 导入 dotenv

# --- 加载环境变量 ---
# 查找项目根目录下的 .env 文件并加载变量
# 这应该在 create_app 之前调用，以便配置可以读取这些变量
# basedir 通常指向项目根目录 (如果 run.py 在根目录)
basedir = os.path.abspath(os.path.dirname(__file__))
dotenv_path = os.path.join(basedir, '.env')
if os.path.exists(dotenv_path):
    print(f"Loading environment variables from: {dotenv_path}")
    load_dotenv(dotenv_path=dotenv_path)
else:
    print("Note: .env file not found, using system environment variables or defaults.")
# -------------------


# --- 导入应用工厂 ---
# 确保 'app' 包或模块中的 __init__.py 定义了 create_app
from app import create_app

# --- 创建 Flask 应用实例 ---
# create_app 会读取 config.py, 而 config.py 会读取已加载的环境变量
app = create_app()


# --- 运行开发服务器 ---
if __name__ == '__main__':
    # 确保 instance 文件夹存在 (SQLite 数据库通常放在这里)
    # 这在 create_app 内部也可能做，但在这里检查也无妨
    try:
        # app.instance_path 是 Flask app 实例的属性，指向 instance 文件夹
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError as e:
        # 如果文件夹已存在或创建失败，记录日志（如果 logger 已配置）或打印
        app.logger.warning(f"Could not create instance folder {app.instance_path}: {e}")
        # print(f"Warning: Could not create instance folder {app.instance_path}: {e}")
        pass # 通常 'exist_ok=True' 已经处理了“已存在”的情况

    # 使用 Flask 内建的开发服务器运行应用
    # debug=True 会启用调试模式和自动重载器
    # host='0.0.0.0' 可以让局域网内的其他设备访问
    # port=5000 是默认端口
    # 注意：Flask 内建服务器不适用于生产环境！生产环境应使用 Gunicorn 或 uWSGI 等 WSGI 服务器。
    print("Starting Flask development server...")
    app.run(host='0.0.0.0', port=5000, debug=True)