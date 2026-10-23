from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    # 签名 session cookie 的密钥；务必用随机长字符串并保持稳定，否则重启后所有登录态失效
    SECRET_KEY: str = ""
    # 部署到 HTTPS 后设为 true，cookie 仅通过 HTTPS 传输
    HTTPS_ONLY: bool = False
    # 登录态有效期（秒），默认 14 天
    SESSION_MAX_AGE: int = 14 * 24 * 60 * 60
    # 初始管理员（数据迁移脚本首次运行时创建，仅当数据库还没有任何用户时）
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123456"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
