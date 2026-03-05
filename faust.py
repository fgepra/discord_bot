import discord
import pymysql
from discord import app_commands
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("FAUST_TOKEN")
GUILD_ID = 1143209391156375713
DB_FILE = "command.db"

custom_commands = {}
guild = discord.Object(id=GUILD_ID)


# ==============================
# MySql 관리
# ==============================

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = int(os.getenv("DB_PORT", 3306))

def get_db_connection():
    try:
        return pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10 # 연결 시도 제한 시간
        )
    except Exception as e:
        print(f"DB 연결 실패: {e}")
        return None

def init_db():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # MySQL은 PRIMARY KEY에 TEXT를 바로 쓸 수 없으므로 VARCHAR(255)를 권장합니다.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS commands (
                name VARCHAR(255) PRIMARY KEY,
                content TEXT NOT NULL
            )
        """)
    conn.commit()
    conn.close()

def load_commands():
    global custom_commands
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT name, content FROM commands")
        rows = cursor.fetchall()
        # DictCursor를 사용하므로 row['name'] 형태로 접근합니다.
        custom_commands = {row['name']: row['content'] for row in rows}
    conn.close()

def save_commands(name, content):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # MySQL의 INSERT OR REPLACE 문법은 ON DUPLICATE KEY UPDATE입니다.
        sql = """
            INSERT INTO commands (name, content)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE content = VALUES(content)
        """
        cursor.execute(sql, (name, content))
    conn.commit()
    conn.close()

def delete_command(name):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM commands WHERE name=%s", (name,))
    conn.commit()
    conn.close()


# ==============================
# 클라이언트
# ==============================

class MyClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):

        init_db()
        load_commands()

        # 기본 명령어 등록
        self.safe_add_command(
            name="파우웅",
            description="가젤 샤프트 확인",
            callback=self.basic_command
        )

        # 저장된 커스텀 명령어 등록
        for name, content in custom_commands.items():
            self.register_dynamic_command(name, content)

        await self.tree.sync(guild=guild)
        print("✅ 완전 동기화 완료")

    # ==========================
    # 안전 등록 함수
    # ==========================

    def safe_add_command(self, name, description, callback):

        # 이미 존재하면 제거
        if self.tree.get_command(name, guild=guild):
            self.tree.remove_command(name, guild=guild)

        self.tree.add_command(
            app_commands.Command(
                name=name,
                description=description,
                callback=callback
            ),
            guild=guild
        )

    def register_dynamic_command(self, name, content):

        async def dynamic_command(interaction: discord.Interaction):
            if interaction.response.is_done():
                return
            await interaction.response.send_message(content)

        self.safe_add_command(
            name=name,
            description=f"{name} 명령어",
            callback=dynamic_command
        )

    async def basic_command(self, interaction: discord.Interaction):
        if interaction.response.is_done():
            return
        await interaction.response.send_message(
            "인간은 노력하는 한 방황하는 법입니다."
        )


client = MyClient()


# ==============================
# 가르치기
# ==============================

@client.tree.command(name="가르치기", description="지식 추가", guild=guild)
@app_commands.describe(이름="지식 이름", 내용="내용")
async def teach(interaction: discord.Interaction, 이름: str, 내용: str):

    if 이름 in custom_commands:
        await interaction.response.send_message("이미 존재하는 지식입니다.")
        return
    
    # 먼저 응답을 보냄
    await interaction.response.send_message(
        f"/{이름} 새로운 지식 추가 처리 중입니다..."
    )

    custom_commands[이름] = 내용
    save_commands(이름, 내용)

    client.register_dynamic_command(이름, 내용)
    await client.tree.sync(guild=guild)

    await interaction.edit_original_response(content=f"/{이름} 멍청한 파우웅은 더 이상 멍청하지 않습니다.")


# ==============================
# 수정
# ==============================

@client.tree.command(name="수정", description="지식 수정", guild=guild)
@app_commands.describe(이름="수정할 지식", 새내용="새로운 지식")
async def edit(interaction: discord.Interaction, 이름: str, 새내용: str):

    if 이름 not in custom_commands:
        await interaction.response.send_message("존재하지 않는 지식입니다.")
        return
    
    # 먼저 응답을 보냄
    await interaction.response.send_message(
        f"/{이름} 지식 수정 처리 중입니다..."
    )

    custom_commands[이름] = 새내용
    save_commands(이름, 새내용)

    client.register_dynamic_command(이름, 새내용)
    await client.tree.sync(guild=guild)

    await interaction.edit_original_response(content=f"/{이름} 올바른 지식으로 수정이 되었습니다.")


# ==============================
# 삭제
# ==============================

@client.tree.command(name="삭제", description="지식 삭제", guild=guild)
@app_commands.describe(이름="삭제할 지식")
async def delete(interaction: discord.Interaction, 이름: str):

    if 이름 not in custom_commands:
        await interaction.response.send_message("존재하지 않는 지식입니다.")
        return

    # 먼저 응답을 보냄
    await interaction.response.send_message(
        f"/{이름} 지식 삭제 처리 중입니다..."
    )

    # 그 다음 작업
    del custom_commands[이름]
    delete_command(이름)

    client.tree.remove_command(이름, guild=guild)
    await client.tree.sync(guild=guild)

    # 메시지 수정
    await interaction.edit_original_response(content=f"/{이름} 멍청한 파우웅은 더욱 멍청해졌습니다.")


client.run(TOKEN)