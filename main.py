import asyncio
import logging
import aiosqlite
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButton
)

# --- SOZLAMALAR ---
API_TOKEN = '8663490544:AAH5GoUWoEEdIT1ZCQYfrir21_qSaC6fPg8'
ADMIN_ID = 7545494003 
VIP_CHANNEL_ID = -1003436465316 
DB_NAME = "vip_users.db"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- TUGMALAR (INTERFEYS) ---

# Pastki asosiy menyu
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💎 VIP Obuna"), KeyboardButton(text="👤 Profilim")],
        [KeyboardButton(text="📞 Admin bilan bog'lanish"), KeyboardButton(text="ℹ️ Ma'lumot")]
    ],
    resize_keyboard=True
)

# Obuna ma'lumoti ostidagi inline tugma
buy_inline = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💳 To'lov rekvizitlari", callback_data="pay_info")]
])

# --- MA'LUMOTLAR BAZASI ---
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users 
                            (user_id INTEGER PRIMARY KEY, expiry_date TEXT)''')
        await db.commit()

# --- ASOSIY HANDLERLAR ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        f"Salom, {message.from_user.full_name}! 👋\nVIP kanal boshqaruv botiga xush kelibsiz.", 
        reply_markup=main_menu
    )

@dp.message(F.text == "💎 VIP Obuna")
async def vip_info(message: types.Message):
    text = (
        "🌟 **VIP Kanal imkoniyatlari:**\n"
        "✅ Eksklyuziv tahlillar va signallar\n"
        "✅ Shaxsiy maslahatlar\n\n"
        "💰 **Tarif:** 30 kun / 50,000 so'm\n\n"
        "To'lov qilish uchun tugmani bosing:"
    )
    await message.answer(text, reply_markup=buy_inline, parse_mode="Markdown")

@dp.callback_query(F.data == "pay_info")
async def send_payment_details(callback: types.CallbackQuery):
    pay_text = (
        "💳 **To'lov rekvizitlari:**\n\n"
        "Karta raqami: `8600000000000000`\n"
        "Ega: **Ism Familiya**\n\n"
        "To'lovdan so'ng chekni (rasmni) shu yerga yuboring."
    )
    await callback.message.answer(pay_text, parse_mode="Markdown")
    await callback.answer()

@dp.message(F.text == "👤 Profilim")
async def user_profile(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT expiry_date FROM users WHERE user_id = ?", (message.from_user.id,))
        row = await cursor.fetchone()
    
    if row:
        await message.answer(f"✅ Obunangiz faol.\n📅 Tugash muddati: `{row[0]}`", parse_mode="Markdown")
    else:
        await message.answer("❌ Sizda faol obuna mavjud emas.")

@dp.message(F.text == "📞 Admin bilan bog'lanish")
async def contact_admin_btn(message: types.Message):
    await message.answer("Savollar bo'yicha: @User_Admin")

@dp.message(F.text == "ℹ️ Ma'lumot")
async def about_bot(message: types.Message):
    await message.answer("Ushbu bot orqali VIP kanalga obunani avtomatik boshqarishingiz mumkin.")

# --- TO'LOVNI QABUL QILISH VA TASDIQLASH ---

@dp.message(F.photo)
async def handle_payment(message: types.Message):
    admin_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Tasdiqlash ✅", callback_data=f"accept_{message.from_user.id}")],
        [InlineKeyboardButton(text="Rad etish ❌", callback_data=f"reject_{message.from_user.id}")]
    ])
    
    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=message.photo[-1].file_id,
        caption=f"📝 **Yangi to'lov!**\nUser: @{message.from_user.username}\nID: `{message.from_user.id}`",
        reply_markup=admin_markup,
        parse_mode="Markdown"
    )
    await message.answer("✅ Rahmat! Chekingiz adminga yuborildi. Tez orada javob olasiz.")

@dp.callback_query(F.data.startswith("accept_"))
async def approve_user(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    # Obuna muddati: 30 kun
    expiry_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, expiry_date) VALUES (?, ?)", (user_id, expiry_date))
        await db.commit()

    # --- BIR MARTALIK (1 KISHI UCHUN) HAVOLA YARATISH ---
    invite_link = await bot.create_chat_invite_link(
        chat_id=VIP_CHANNEL_ID, 
        member_limit=1 # Havoladan faqat 1 kishi foydalana oladi
    )
    
    await bot.send_message(
        user_id, 
        f"🥳 To'lovingiz tasdiqlandi! VIP kanalga kirish uchun quyidagi bir martalik havolani bosing:\n\n{invite_link.invite_link}"
    )
    await callback.message.edit_caption(caption=f"✅ Tasdiqlandi\nMuddat: {expiry_date}")

@dp.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    await bot.send_message(user_id, "❌ Uzr, siz yuborgan chek tasdiqlanmadi.")
    await callback.message.edit_caption(caption="❌ Rad etildi")

# --- AVTOMATIK TOZALASH (HAR 1 SOATDA) ---

async def check_subscriptions():
    while True:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute("SELECT user_id FROM users WHERE expiry_date <= ?", (now,))
            expired_users = await cursor.fetchall()
            
            for (u_id,) in expired_users:
                try:
                    await bot.ban_chat_member(VIP_CHANNEL_ID, u_id)
                    await bot.unban_chat_member(VIP_CHANNEL_ID, u_id)
                    await bot.send_message(u_id, "⚠️ Sizning VIP obunangiz tugadi. Kanalga qayta kirish uchun obunani yangilang.")
                    await db.execute("DELETE FROM users WHERE user_id = ?", (u_id,))
                except Exception as e:
                    logging.error(f"Error removing {u_id}: {e}")
            await db.commit()
        await asyncio.sleep(3600) # 1 soat kutish

# --- ASOSIY ISHGA TUSHIRISH ---

async def main():
    await init_db()
    asyncio.create_task(check_subscriptions()) # Obuna tekshiruvini fonda yoqish
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi")