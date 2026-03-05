import discord
import pymysql
from discord import app_commands
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("FAUST_TOKEN")
GUILD_ID = 1143209391156375713

custom_commands = {}
guild = discord.Object(id=GUILD_ID)

# ==============================
# MySQL 관리 (기존과 동일)
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
            connect_timeout=10
        )
    except Exception as e:
        print(f"DB 연결 실패: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if not conn: return
    with conn.cursor() as cursor:
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
    if not conn: return
    with conn.cursor() as cursor:
        cursor.execute("SELECT name, content FROM commands")
        rows = cursor.fetchall()
        custom_commands = {row['name']: row['content'] for row in rows}
    conn.close()

def save_commands(name, content):
    conn = get_db_connection()
    if not conn: return
    with conn.cursor() as cursor:
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
    if not conn: return
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM commands WHERE name=%s", (name,))
    conn.commit()
    conn.close()


# ==============================
# 클라이언트 (수정됨)
# ==============================

class MyClient(discord.Client):
    def __init__(self):
        # 1. 메시지 내용을 읽기 위해 intents.message_content 활성화
        intents = discord.Intents.default()
        intents.message_content = True 
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        init_db()
        load_commands()

        # 기존 슬래시 명령어 등록 기능 유지
        self.safe_add_command(
            name="파우웅",
            description="가젤 샤프트 확인",
            callback=self.basic_command
        )

        # 저장된 지식들도 슬래시 명령어로 일단 등록은 해둠 (기존 기능 유지)
        for name, content in custom_commands.items():
            self.register_dynamic_command(name, content)

        await self.tree.sync(guild=guild)
        print("✅ 완전 동기화 완료 및 메시지 반응형 활성화")

    # 2. 메시지가 올라올 때마다 지식 DB에 있는지 확인하는 함수 추가
    async def on_message(self, message):
        if message.author == self.user:  # 봇이 쓴 글은 무시
            return

        # 만약 채팅 내용이 가르친 '이름'과 정확히 일치한다면 대답
        if message.content in custom_commands:
            await message.channel.send(custom_commands[message.content])

    def safe_add_command(self, name, description, callback):
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
            if interaction.response.is_done(): return
            await interaction.response.send_message(content)

        self.safe_add_command(
            name=name,
            description=f"{name} 명령어",
            callback=dynamic_command
        )

    async def basic_command(self, interaction: discord.Interaction):
        if interaction.response.is_done(): return
        await interaction.response.send_message("인간은 노력하는 한 방황하는 법입니다.")

client = MyClient()

# ==============================
# 가르치기 / 수정 / 삭제 (기존 슬래시 명령어 유지)
# ==============================

@client.tree.command(name="가르치기", description="지식 추가", guild=guild)
@app_commands.describe(이름="지식 이름", 내용="내용")
async def teach(interaction: discord.Interaction, 이름: str, 내용: str):
    if 이름 in custom_commands:
        await interaction.response.send_message("이미 존재하는 지식입니다.")
        return
    
    await interaction.response.send_message(f"'{이름}' 지식을 배우는 중입니다...")

    custom_commands[이름] = 내용
    save_commands(이름, 내용)

    # 슬래시 명령어로도 등록 (시간이 걸릴 수 있음)
    client.register_dynamic_command(이름, 내용)
    await client.tree.sync(guild=guild)

    await interaction.edit_original_response(content=f"이제 '{이름}'이라고 말하면 대답해 드릴게요!")

@client.tree.command(name="수정", description="지식 수정", guild=guild)
@app_commands.describe(이름="수정할 지식", 새내용="새로운 지식")
async def edit(interaction: discord.Interaction, 이름: str, 새내용: str):
    if 이름 not in custom_commands:
        await interaction.response.send_message("존재하지 않는 지식입니다.")
        return
    
    await interaction.response.send_message(f"'{이름}' 지식을 수정 중입니다...")
    custom_commands[이름] = 새내용
    save_commands(이름, 새내용)
    client.register_dynamic_command(이름, 새내용)
    await client.tree.sync(guild=guild)
    await interaction.edit_original_response(content=f"'{이름}' 지식을 수정했습니다.")

@client.tree.command(name="삭제", description="지식 삭제", guild=guild)
@app_commands.describe(이름="삭제할 지식")
async def delete(interaction: discord.Interaction, 이름: str):
    if 이름 not in custom_commands:
        await interaction.response.send_message("존재하지 않는 지식입니다.")
        return

    await interaction.response.send_message(f"'{이름}' 지식을 잊는 중입니다...")
    del custom_commands[이름]
    delete_command(이름)
    client.tree.remove_command(이름, guild=guild)
    await client.tree.sync(guild=guild)
    await interaction.edit_original_response(content=f"이제 '{이름}'이(가) 무엇인지 기억나지 않네요.")

client.run(TOKEN)