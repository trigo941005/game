import pygame
import random
import sys
import pickle
import os
import tkinter as tk
from tkinter import filedialog

# --- 遊戲設定與常數 ---
WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 768
FPS = 60

# 顏色定義 (R, G, B)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BG_COLOR = (30, 30, 30)       # 深灰背景
PANEL_COLOR = (50, 50, 50)    # 區塊背景
BUTTON_COLOR = (70, 130, 180) # 按鈕藍
BUTTON_HOVER = (100, 149, 237)
TEXT_COLOR = (240, 240, 240)
GREEN = (50, 205, 50)
RED = (220, 20, 60)
GOLD = (255, 215, 0)

# --- 音效系統 ---
SOUNDS = {}

def play_sound(name):
    """播放音效的安全函式"""
    if name in SOUNDS:
        SOUNDS[name].play()

def init_audio():
    """初始化音效與背景音樂"""
    pygame.mixer.init()
    
    # 載入背景音樂 (BGM)
    try:
        pygame.mixer.music.load('bgm.mp3')
        pygame.mixer.music.set_volume(0.4) # 音量 40%
        pygame.mixer.music.play(-1) # -1 代表無限循環
    except Exception:
        print("提示：未找到背景音樂 (bgm.mp3)")

    # 載入音效 (SFX)
    sfx_files = {
        'click': 'click.wav',
        'cash': 'cash.wav',
        'success': 'success.wav',
        'fail': 'fail.wav',
        'alert': 'alert.wav',
        'win': 'win.wav',
        'lose': 'lose.wav'
    }
    for name, filename in sfx_files.items():
        try:
            SOUNDS[name] = pygame.mixer.Sound(filename)
            SOUNDS[name].set_volume(0.6)
        except Exception:
            pass # 找不到檔案就忽略，不影響遊戲

# --- 核心邏輯類別 (與文字版類似) ---

class Bot:
    def __init__(self, level=1):
        self.level = level
        self.influence = level * 25 # 平衡調整：提升基礎影響力
        self.stealth = 100 - (level * 5)
        self.is_banned = False
        self.max_uses = 1 + (level // 2) # 每日使用次數限制 (Lv1-2: 1次, Lv3-4: 2次...)
        self.used_today = 0

    def get_upgrade_cost(self):
        return self.level * 150

    def is_available(self):
        return not self.is_banned and self.used_today < self.max_uses

    def reset_daily(self):
        self.used_today = 0

    def upgrade(self):
        self.level += 1
        self.influence = self.level * 25
        self.stealth = min(95, 100 - (self.level * 5) + (self.level * 2))
        self.max_uses = 1 + (self.level // 2)

class Mission:
    def __init__(self, name, difficulty, reward, required_influence):
        self.name = name
        self.difficulty = difficulty
        self.reward = reward
        self.required_influence = required_influence

class Achievement:
    def __init__(self, key, title, desc, condition):
        self.key = key
        self.title = title
        self.desc = desc
        self.condition = condition
        self.unlocked = False

class GameState:
    """管理遊戲數據與邏輯"""
    def __init__(self, difficulty="Standard"):
        self.difficulty = difficulty
        if difficulty == "Easy":
            self.money = 2000
            self.risk_modifier = 0.7
            self.target_reputation = 3000
        elif difficulty == "Hard":
            self.money = 500
            self.risk_modifier = 1.3
            self.target_reputation = 10000
        else:
            self.money = 1000
            self.risk_modifier = 1.0
            self.target_reputation = 5000

        self.bots = [Bot() for _ in range(5)]
        self.available_missions = []
        self.day = 1
        self.reputation = 0
        self.pending_money = 0 # 待結算資金 (隔日入帳)
        self.selected_mission = None # 當前選中的任務（等待選擇策略）
        self.deploy_count = 0 # 準備派出的帳號數量
        self.game_over = False
        self.victory = False
        self.logs = [f"歡迎來到《網路水軍模擬器》！難度: {difficulty}", "請購買帳號或選擇任務開始。"]
        
        # --- 成就系統 ---
        self.achievements = [
            Achievement("bots_10", "初出茅廬", "擁有 10 個帳號", lambda g: len(g.bots) >= 10),
            Achievement("bots_50", "水軍指揮官", "擁有 50 個帳號", lambda g: len(g.bots) >= 50),
            Achievement("bots_100", "百萬大軍", "擁有 100 個帳號", lambda g: len(g.bots) >= 100),
            Achievement("level_3", "技術升級", "擁有 Lv3 以上帳號", lambda g: any(b.level >= 3 for b in g.bots)),
            Achievement("level_5", "頂尖駭客", "擁有 Lv5 以上帳號", lambda g: any(b.level >= 5 for b in g.bots)),
            Achievement("level_10", "網軍教父", "擁有 Lv10 以上帳號", lambda g: any(b.level >= 10 for b in g.bots)),
            Achievement("money_10k", "資本巨鱷", "持有資金超過 $10000", lambda g: g.money >= 10000),
            Achievement("money_100k", "富可敵國", "持有資金超過 $100000", lambda g: g.money >= 100000),
            Achievement("rep_2k", "意見領袖", "聲望達到 2000", lambda g: g.reputation >= 2000),
            Achievement("rep_10k", "輿論之神", "聲望達到 10000", lambda g: g.reputation >= 10000),
        ]
        self.achievement_queue = [] # 等待顯示的成就
        self.achievement_timer = 0  # 通知顯示計時器
        self.current_achievement_msg = None

        self.generate_missions()

    def log(self, message):
        """新增訊息到日誌視窗"""
        self.logs.append(message)
        if len(self.logs) > 12: # 只保留最近 12 條訊息
            self.logs.pop(0)

    def generate_missions(self):
        mission_types = [
            ("引導論壇議題風向", 2, 600, 100),
            ("製造假民意支持特定政策", 4, 1200, 250),
            ("煽動社群群體對立", 6, 2500, 500),
            ("抹黑競爭對手公眾形象", 8, 4000, 800),
            ("洗白企業重大醜聞", 10, 8000, 1200),
            ("操縱選舉輿論走向", 15, 20000, 2500),
            ("散佈恐慌性假消息", 12, 12000, 1500)
        ]
        self.available_missions = []
        
        # 根據聲望篩選可接的任務類型
        valid_types = [m for m in mission_types if self.reputation >= (m[1] * 5) - 20]
        if not valid_types:
            valid_types = [mission_types[0], mission_types[1]]

        # 隨機生成 3 到 5 個任務
        num_missions = random.randint(3, 5)
        for _ in range(num_missions):
            m_data = random.choice(valid_types)
            # 數值微調 (波動 +/- 10%)
            variance = random.uniform(0.9, 1.1)
            self.available_missions.append(Mission(
                m_data[0],
                m_data[1],
                int(m_data[2] * variance),
                int(m_data[3] * variance)
            ))

    def check_status(self):
        """檢查遊戲是否結束"""
        if self.game_over: return

        # 勝利條件：聲望達標
        if self.reputation >= self.target_reputation:
            self.game_over = True
            self.victory = True
            play_sound('win')
        
        # 失敗條件：沒錢買帳號 且 沒有活著的帳號
        active_bots = [b for b in self.bots if not b.is_banned]
        if (self.money + self.pending_money) < 100 and len(active_bots) == 0:
            self.game_over = True
            self.victory = False
            play_sound('lose')

    def check_achievements(self):
        """檢查是否有新成就解鎖"""
        for ach in self.achievements:
            if not ach.unlocked and ach.condition(self):
                ach.unlocked = True
                msg = f"成就解鎖：{ach.title} ({ach.desc})"
                self.achievement_queue.append(msg)
                self.log(f"★ {msg}")
                play_sound('success')

    def buy_bot(self, count=1):
        cost = 100 * count
        if self.money >= cost:
            self.money -= cost
            for _ in range(count):
                self.bots.append(Bot())
            self.log(f"購買成功！新增 {count} 個帳號。")
            play_sound('cash')
        else:
            self.log(f"資金不足！需要 ${cost}。")
        self.check_status()
        self.check_achievements()

    def upgrade_bot(self, bot):
        if bot.is_banned:
            self.log("無法升級已封鎖帳號。")
            return
        cost = bot.get_upgrade_cost()
        if self.money >= cost:
            self.money -= cost
            bot.upgrade()
            self.log(f"升級成功！Lv{bot.level} (花費 ${cost})")
            play_sound('cash')
        else:
            self.log(f"資金不足！升級需 ${cost}")
        self.check_status()
        self.check_achievements()

    def upgrade_all_bots(self):
        """批量升級所有可用帳號"""
        active_bots = [b for b in self.bots if not b.is_banned]
        # 優先升級低等級的 (便宜)
        active_bots.sort(key=lambda b: b.level)
        
        count = 0
        total_cost = 0
        for bot in active_bots:
            cost = bot.get_upgrade_cost()
            if self.money >= cost:
                self.money -= cost
                bot.upgrade()
                total_cost += cost
                count += 1
            else:
                break # 沒錢了
        
        if count > 0:
            self.log(f"批量升級: {count} 個帳號 (花費 ${total_cost})")
            play_sound('cash')
        else:
            self.log("資金不足以升級任何帳號")
        self.check_status()
        self.check_achievements()

    def execute_mission(self, mission, strategy="normal", bot_count=0):
        # 篩選可用帳號並優先使用等級高的 (或是隨意，這裡用預設順序)
        available_bots = [b for b in self.bots if b.is_available()]
        # 根據等級排序，優先派出高等級帳號
        available_bots.sort(key=lambda b: b.level, reverse=True)
        
        bots_to_use = available_bots[:bot_count]
        for b in bots_to_use:
            b.used_today += 1
            
        total_influence = sum(b.influence for b in bots_to_use)
        
        # 策略加成計算
        risk_factor = 1.0
        inf_factor = 1.0
        strat_name = "一般操作"

        if strategy == "spam":
            inf_factor = 1.5
            risk_factor = 2.0
            strat_name = "暴力洗版"
        elif strategy == "troll":
            inf_factor = 0.8
            risk_factor = 0.5
            strat_name = "反串釣魚"
        
        final_influence = int(total_influence * inf_factor)
        
        self.log(f"[{strat_name}] 執行: {mission.name}")
        self.log(f"影響力: {final_influence} (原:{total_influence}) / 需求: {mission.required_influence}")

        if final_influence >= mission.required_influence:
            self.pending_money += mission.reward
            self.reputation += mission.difficulty
            self.log(f"任務成功！報酬 ${mission.reward} 將於明日入帳")
            play_sound('success')
            self.trigger_ban_wave(mission.difficulty * risk_factor)
        else:
            self.reputation = max(0, self.reputation - 2)
            self.log("任務失敗！影響力不足。")
            play_sound('fail')
            self.trigger_ban_wave((mission.difficulty // 2) * risk_factor)

        # 任務執行後移除
        if mission in self.available_missions:
            self.available_missions.remove(mission)
        self.check_status()
        self.check_achievements()

    def trigger_ban_wave(self, risk_level):
        banned_count = 0
        for bot in self.bots:
            if bot.is_banned: continue
            # 簡單的機率計算
            detection_chance = (risk_level * 5 * self.risk_modifier) - (bot.stealth * 0.1)
            if random.randint(0, 100) < detection_chance:
                bot.is_banned = True
                banned_count += 1
        
        if banned_count > 0:
            self.log(f"警告！平台反制，損失了 {banned_count} 個帳號！")
            play_sound('alert')
        self.check_status()
        self.check_achievements()

    def next_day(self):
        self.day += 1
        
        # 結算昨日收益
        if self.pending_money > 0:
            self.money += self.pending_money
            self.log(f"昨日收益 ${self.pending_money} 已入帳")
            play_sound('cash')
            self.pending_money = 0

        # 清理被封鎖的帳號
        for b in self.bots:
            b.reset_daily()
        original_count = len(self.bots)
        self.bots = [b for b in self.bots if not b.is_banned]
        removed = original_count - len(self.bots)
        
        self.generate_missions()
        self.log(f"=== 第 {self.day} 天 ===")
        if removed > 0:
            self.log(f"昨日共有 {removed} 個帳號被永久封鎖。")
        self.check_status()
        self.check_achievements()

    def save_game(self):
        """儲存遊戲狀態"""
        data = {
            'money': self.money,
            'pending_money': self.pending_money,
            'bots': self.bots,
            'available_missions': self.available_missions,
            'day': self.day,
            'reputation': self.reputation,
            'difficulty': self.difficulty,
            'risk_modifier': self.risk_modifier,
            'target_reputation': self.target_reputation,
            'logs': self.logs,
            'unlocked_achievements': [a.key for a in self.achievements if a.unlocked]
        }
        try:
            with open('savegame.pkl', 'wb') as f:
                pickle.dump(data, f)
            self.log("遊戲進度已儲存！")
        except Exception as e:
            self.log(f"儲存失敗: {e}")

    def load_game(self):
        """讀取遊戲狀態"""
        # 使用 tkinter 彈出檔案選擇視窗
        try:
            root = tk.Tk()
            root.withdraw() # 隱藏主視窗
            root.attributes('-topmost', True) # 確保視窗在最上層
            
            file_path = filedialog.askopenfilename(
                title="選擇存檔",
                filetypes=[("存檔檔案", "*.pkl"), ("所有檔案", "*.*")],
                initialdir=os.getcwd()
            )
            root.destroy()
        except Exception as e:
            self.log(f"開啟檔案視窗失敗: {e}")
            return

        if not file_path:
            self.log("未選擇檔案。")
            return

        try:
            with open(file_path, 'rb') as f:
                data = pickle.load(f)
            
            # 更新當前物件屬性
            self.__dict__.update(data)
            
            # 資料遷移：確保舊存檔的機器人有新屬性
            for b in self.bots:
                if not hasattr(b, 'max_uses'):
                    b.max_uses = 1 + (b.level // 2)
                if not hasattr(b, 'used_today'):
                    b.used_today = 0
                b.influence = b.level * 25 # 更新數值平衡
            if not hasattr(self, 'pending_money'):
                self.pending_money = 0

            # 恢復成就狀態
            if hasattr(self, 'unlocked_achievements'):
                for ach in self.achievements:
                    if ach.key in self.unlocked_achievements:
                        ach.unlocked = True

            # 重置暫時狀態 (避免讀檔後介面卡住)
            self.selected_mission = None
            self.game_over = False
            self.victory = False
            
            self.log(f"已讀取: {os.path.basename(file_path)}")
        except Exception as e:
            self.log(f"讀取失敗: {e}")

# --- UI 輔助類別 ---

class Button:
    def __init__(self, x, y, w, h, text, callback):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.callback = callback
        self.color = BUTTON_COLOR

    def draw(self, surface, font):
        mouse_pos = pygame.mouse.get_pos()
        # 滑鼠懸停變色效果
        current_color = BUTTON_HOVER if self.rect.collidepoint(mouse_pos) else self.color
        
        pygame.draw.rect(surface, current_color, self.rect, border_radius=8)
        pygame.draw.rect(surface, WHITE, self.rect, 2, border_radius=8) # 邊框
        
        text_surf = font.render(self.text, True, WHITE)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def check_click(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                play_sound('click')
                self.callback()

# --- 主程式 ---

def get_chinese_font():
    """嘗試獲取系統中的中文字型"""
    # 常見的中文字型名稱列表 (Windows, Mac, Linux)
    font_names = ["microsoftjhenghei", "pingfangtc", "heiti", "simhei", "arialunicode"]
    font_path = pygame.font.match_font(font_names)
    
    if font_path:
        return pygame.font.Font(font_path, 24)
    else:
        print("警告：找不到中文字型，文字可能無法顯示。")
        return pygame.font.Font(None, 24)

def account_management_screen(screen, game, font, title_font):
    """帳號管理頁面"""
    clock = pygame.time.Clock()
    running = True
    page = 0
    items_per_page = 10
    
    # 內部按鈕
    btn_back = Button(50, 700, 100, 50, "返回", lambda: None)
    btn_upgrade_all = Button(170, 700, 250, 50, "一鍵升級 (低等優先)", game.upgrade_all_bots)

    while running:
        screen.fill(BG_COLOR)
        
        # 標題
        screen.blit(title_font.render("帳號管理中心", True, GOLD), (50, 30))
        screen.blit(font.render(f"資金: ${game.money} | 帳號總數: {len(game.bots)}", True, WHITE), (50, 80))

        # 列表標頭
        headers = ["ID", "等級", "影響力", "隱蔽值", "今日用量", "狀態", "升級費用"]
        x_pos = [50, 120, 200, 320, 440, 580, 700]
        pygame.draw.line(screen, WHITE, (40, 120), (980, 120), 2)
        for i, h in enumerate(headers):
            screen.blit(font.render(h, True, GOLD), (x_pos[i], 130))
        pygame.draw.line(screen, WHITE, (40, 160), (980, 160), 2)

        # 列表內容
        total_pages = (len(game.bots) - 1) // items_per_page + 1
        if page >= total_pages: page = max(0, total_pages - 1)
        
        start = page * items_per_page
        end = min(start + items_per_page, len(game.bots))
        
        y = 180
        for i in range(start, end):
            bot = game.bots[i]
            color = WHITE
            status = "正常"
            cost_str = f"${bot.get_upgrade_cost()}"
            
            if bot.is_banned:
                color = RED
                status = "已封鎖"
                cost_str = "-"
            
            row = [
                f"#{i+1}", f"Lv.{bot.level}", f"{bot.influence}", 
                f"{bot.stealth}", f"{bot.used_today}/{bot.max_uses}", 
                status, cost_str
            ]
            
            for j, txt in enumerate(row):
                screen.blit(font.render(txt, True, color), (x_pos[j], y))
            
            # 單個升級按鈕
            if not bot.is_banned:
                btn_rect = pygame.Rect(850, y, 80, 30)
                pygame.draw.rect(screen, BUTTON_COLOR, btn_rect, border_radius=5)
                screen.blit(font.render("升級", True, WHITE), (865, y+2))
            
            y += 50

        # 頁碼與翻頁箭頭
        page_str = f"頁數: {page+1}/{max(1, total_pages)}"
        screen.blit(font.render(page_str, True, WHITE), (850, 80))
        
        # 繪製翻頁按鈕區域 (簡單圖示)
        prev_rect = pygame.Rect(810, 80, 30, 30)
        next_rect = pygame.Rect(980, 80, 30, 30)
        pygame.draw.polygon(screen, WHITE, [(830, 85), (830, 105), (810, 95)])
        pygame.draw.polygon(screen, WHITE, [(980, 85), (980, 105), (1000, 95)])

        btn_back.draw(screen, font)
        btn_upgrade_all.draw(screen, font)

        pygame.display.flip()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if btn_back.rect.collidepoint(event.pos):
                    running = False
                    play_sound('click')
                if btn_upgrade_all.rect.collidepoint(event.pos):
                    btn_upgrade_all.callback()
                
                # 翻頁
                if prev_rect.collidepoint(event.pos) and page > 0:
                    page -= 1
                    play_sound('click')
                if next_rect.collidepoint(event.pos) and page < total_pages - 1:
                    page += 1
                    play_sound('click')
                
                # 單個升級點擊偵測
                y_check = 180
                for i in range(start, end):
                    bot = game.bots[i]
                    if not bot.is_banned:
                        btn_rect = pygame.Rect(850, y_check, 80, 30)
                        if btn_rect.collidepoint(event.pos):
                            game.upgrade_bot(bot)
                    y_check += 50
        
        clock.tick(FPS)

def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("網路水軍模擬器 v0.2 (Pygame Edition)")
    init_audio() # 初始化音效系統
    clock = pygame.time.Clock()
    
    # 設定字型
    font = get_chinese_font()
    title_font = pygame.font.Font(pygame.font.match_font(["microsoftjhenghei", "simhei"]), 36)

    # --- 難度選擇畫面 ---
    selected_difficulty = None
    
    def set_diff(d):
        nonlocal selected_difficulty
        selected_difficulty = d

    cx = WINDOW_WIDTH // 2 - 150
    btn_easy = Button(cx, 300, 300, 50, "簡單 (資金$2000 / 風險低)", lambda: set_diff("Easy"))
    btn_standard = Button(cx, 370, 300, 50, "標準 (資金$1000 / 標準)", lambda: set_diff("Standard"))
    btn_hard = Button(cx, 440, 300, 50, "困難 (資金$500 / 風險高)", lambda: set_diff("Hard"))

    while selected_difficulty is None:
        screen.fill(BG_COLOR)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            btn_easy.check_click(event)
            btn_standard.check_click(event)
            btn_hard.check_click(event)
        
        title_surf = title_font.render("請選擇遊戲難度", True, GOLD)
        screen.blit(title_surf, (WINDOW_WIDTH//2 - title_surf.get_width()//2, 200))
        
        btn_easy.draw(screen, font)
        btn_standard.draw(screen, font)
        btn_hard.draw(screen, font)
        
        pygame.display.flip()
        clock.tick(FPS)

    game = GameState(selected_difficulty)

    # 建立按鈕
    btn_buy_1 = Button(50, 680, 105, 50, "買1 ($100)", lambda: game.buy_bot(1))
    btn_buy_5 = Button(165, 680, 105, 50, "買5 ($500)", lambda: game.buy_bot(5))
    btn_next = Button(280, 680, 200, 50, "休息一天 (刷新)", game.next_day)
    btn_save = Button(500, 680, 100, 50, "存檔", game.save_game)
    btn_load = Button(610, 680, 100, 50, "讀檔", game.load_game)
    btn_manage = Button(720, 680, 150, 50, "帳號管理", lambda: account_management_screen(screen, game, font, title_font))

    # --- 策略選擇介面按鈕 ---
    # 調整數量按鈕
    def adjust_deploy(delta):
        available = len([b for b in game.bots if b.is_available()])
        new_count = game.deploy_count + delta
        if 1 <= new_count <= available:
            game.deploy_count = new_count
            play_sound('click')

    btn_dec = Button(312, 340, 50, 40, "-", lambda: adjust_deploy(-1))
    btn_inc = Button(450, 340, 50, 40, "+", lambda: adjust_deploy(1))

    def run_strat(s):
        if game.selected_mission:
            game.execute_mission(game.selected_mission, s, game.deploy_count)
            game.selected_mission = None

    # 調整策略按鈕位置 (往下移以容納數量選擇器)
    btn_strat_spam = Button(312, 390, 400, 50, "暴力洗版 (影響力+++ / 風險高)", lambda: run_strat("spam"))
    btn_strat_norm = Button(312, 450, 400, 50, "一般帶風向 (標準)", lambda: run_strat("normal"))
    btn_strat_troll = Button(312, 510, 400, 50, "反串釣魚 (影響力- / 風險低)", lambda: run_strat("troll"))
    btn_cancel = Button(312, 580, 400, 50, "取消", lambda: setattr(game, 'selected_mission', None))

    running = True
    while running:
        # 1. 事件處理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            # 如果遊戲結束或正在選擇策略，攔截一般操作
            if game.game_over:
                pass # 遊戲結束時不處理任何遊戲內操作
            elif game.selected_mission:
                btn_dec.check_click(event)
                btn_inc.check_click(event)
                btn_strat_spam.check_click(event)
                btn_strat_norm.check_click(event)
                btn_strat_troll.check_click(event)
                btn_cancel.check_click(event)
            else:
                # 一般模式
                btn_buy_1.check_click(event)
                btn_buy_5.check_click(event)
                btn_next.check_click(event)
                btn_save.check_click(event)
                btn_load.check_click(event)
                btn_manage.check_click(event)

                # 處理任務列表的點擊
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    # 檢查是否點擊了任務區域
                    for i, mission in enumerate(game.available_missions):
                        mission_rect = pygame.Rect(50, 150 + i * 70, 600, 60)
                        if mission_rect.collidepoint(mx, my):
                            game.selected_mission = mission # 進入策略選擇模式
                            
                            # 智慧預設：計算剛好滿足需求的數量
                            available_bots = [b for b in game.bots if b.is_available()]
                            available_bots.sort(key=lambda b: b.level, reverse=True)
                            
                            needed_count = 0
                            current_inf = 0
                            for b in available_bots:
                                if current_inf >= mission.required_influence:
                                    break
                                current_inf += b.influence
                                needed_count += 1
                            
                            # 至少派 1 個，除非沒人
                            game.deploy_count = max(1, needed_count) if available_bots else 0
                            break
                
                # 處理帳號升級點擊 (點擊方塊)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    start_x, start_y = 50, 570
                    box_size, gap = 15, 5
                    for idx, bot in enumerate(game.bots):
                        bx = start_x + (idx % 30) * (box_size + gap)
                        by = start_y + (idx // 30) * (box_size + gap)
                        if pygame.Rect(bx, by, box_size, box_size).collidepoint(mx, my):
                            play_sound('click')
                            game.upgrade_bot(bot)

        # 2. 畫面繪製
        screen.fill(BG_COLOR)

        # --- 頂部資訊欄 ---
        header_text = f"第 {game.day} 天 | 資金: ${game.money} (+${game.pending_money}) | 聲望: {game.reputation}/{game.target_reputation} | 帳號: {len(game.bots)}"
        header_surf = title_font.render(header_text, True, GOLD)
        screen.blit(header_surf, (50, 30))

        # --- 左側：任務列表 ---
        screen.blit(font.render("可用任務 (點擊執行):", True, WHITE), (50, 110))
        
        for i, mission in enumerate(game.available_missions):
            rect = pygame.Rect(50, 150 + i * 70, 600, 60)
            
            # 任務滑鼠懸停效果
            color = PANEL_COLOR
            if rect.collidepoint(pygame.mouse.get_pos()):
                color = (70, 70, 70)
            
            pygame.draw.rect(screen, color, rect, border_radius=5)
            
            # 任務文字
            info_text = f"{mission.name}"
            detail_text = f"難度: {mission.difficulty} | 報酬: ${mission.reward} | 需求影響力: {mission.required_influence}"
            
            screen.blit(font.render(info_text, True, GREEN), (rect.x + 10, rect.y + 10))
            screen.blit(font.render(detail_text, True, TEXT_COLOR), (rect.x + 10, rect.y + 35))

        # --- 左側下方：帳號可視化 ---
        viz_y = 510
        screen.blit(font.render("帳號部隊狀態:", True, WHITE), (50, viz_y))
        
        # 統計數據
        active_bots = [b for b in game.bots if not b.is_banned]
        total_inf = sum(b.influence for b in active_bots)
        # 計算今日可用總次數
        total_uses_left = sum(b.max_uses - b.used_today for b in active_bots)
        
        stats_text = f"總影響力: {total_inf}"
        screen.blit(font.render(stats_text, True, GOLD), (200, viz_y))
        screen.blit(font.render(f"剩餘行動力: {total_uses_left}", True, (100, 255, 255)), (200, viz_y + 25))
        
        # 繪製方塊
        start_x, start_y = 50, viz_y + 60
        box_size, gap = 15, 5
        cols = 30
        
        for idx, bot in enumerate(game.bots):
            row = idx // cols
            col = idx % cols
            bx = start_x + col * (box_size + gap)
            by = start_y + row * (box_size + gap)
            
            color = GREEN
            if bot.is_banned: color = RED
            elif bot.level > 1: color = (0, 255, 255)
            # 如果今日次數用完，變暗
            if not bot.is_banned and bot.used_today >= bot.max_uses:
                color = (50, 100, 50)
            
            b_rect = pygame.Rect(bx, by, box_size, box_size)
            pygame.draw.rect(screen, color, b_rect)
            
            if b_rect.collidepoint(pygame.mouse.get_pos()):
                pygame.draw.rect(screen, WHITE, b_rect, 2)
                cost = bot.get_upgrade_cost()
                tip = f"Lv{bot.level} Inf:{bot.influence} 用量:{bot.used_today}/{bot.max_uses} [升級 ${cost}]" if not bot.is_banned else "已封鎖"
                tip_surf = font.render(tip, True, WHITE)
                screen.blit(tip_surf, (bx, by - 25))

        # --- 右側：系統日誌 ---
        log_bg = pygame.Rect(680, 110, 300, 550)
        pygame.draw.rect(screen, BLACK, log_bg)
        pygame.draw.rect(screen, (100, 100, 100), log_bg, 2) # 邊框
        
        screen.blit(font.render("系統日誌:", True, WHITE), (680, 80))
        
        log_y = 120
        for log in game.logs:
            log_surf = font.render(log, True, (200, 200, 200))
            screen.blit(log_surf, (690, log_y))
            log_y += 35

        # --- 底部：按鈕 ---
        btn_buy_1.draw(screen, font)
        btn_buy_5.draw(screen, font)
        btn_next.draw(screen, font)
        btn_save.draw(screen, font)
        btn_load.draw(screen, font)
        btn_manage.draw(screen, font)

        # --- 策略選擇彈出視窗 (Overlay) ---
        if game.selected_mission:
            # 半透明遮罩
            overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
            overlay.set_alpha(180)
            overlay.fill(BLACK)
            screen.blit(overlay, (0, 0))
            
            # 對話框背景
            dialog_rect = pygame.Rect(262, 200, 500, 460) # 加高背景
            pygame.draw.rect(screen, PANEL_COLOR, dialog_rect, border_radius=12)
            pygame.draw.rect(screen, WHITE, dialog_rect, 2, border_radius=12)
            
            # 標題與說明
            screen.blit(title_font.render("選擇言論操控手段", True, GOLD), (360, 220))
            screen.blit(font.render(f"目標: {game.selected_mission.name}", True, WHITE), (300, 280))
            screen.blit(font.render("請選擇派出數量與策略：", True, (200, 200, 200)), (300, 310))
            
            # --- 數量選擇控制 ---
            # 計算預計影響力
            avail_bots = [b for b in game.bots if b.is_available()]
            avail_bots.sort(key=lambda b: b.level, reverse=True)
            selected_bots = avail_bots[:game.deploy_count]
            current_inf = sum(b.influence for b in selected_bots)

            screen.blit(font.render(f"{game.deploy_count}", True, WHITE), (390, 348))
            screen.blit(font.render(f"/ {len(avail_bots)} (可用)", True, (150, 150, 150)), (420, 348))
            screen.blit(font.render(f"預計基礎影響力: {current_inf}", True, GOLD), (520, 348))
            btn_dec.draw(screen, font)
            btn_inc.draw(screen, font)

            # 策略按鈕
            btn_strat_spam.draw(screen, font)
            btn_strat_norm.draw(screen, font)
            btn_strat_troll.draw(screen, font)
            btn_cancel.draw(screen, font)

        # --- 成就通知彈出視窗 ---
        if game.achievement_timer > 0:
            game.achievement_timer -= 1
            # 繪製通知框
            notif_rect = pygame.Rect(WINDOW_WIDTH // 2 - 250, 80, 500, 50)
            pygame.draw.rect(screen, (50, 50, 50), notif_rect, border_radius=10)
            pygame.draw.rect(screen, GOLD, notif_rect, 3, border_radius=10)
            
            msg_surf = font.render(game.current_achievement_msg, True, GOLD)
            msg_rect = msg_surf.get_rect(center=notif_rect.center)
            screen.blit(msg_surf, msg_rect)
        elif game.achievement_queue:
            game.current_achievement_msg = game.achievement_queue.pop(0)
            game.achievement_timer = 180 # 顯示 3 秒 (60 FPS * 3)

        # --- 遊戲結束畫面 (Game Over Screen) ---
        if game.game_over:
            overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
            overlay.set_alpha(220)
            overlay.fill(BLACK)
            screen.blit(overlay, (0, 0))
            
            if game.victory:
                msg1 = "恭喜！你已成為輿論之王！"
                msg2 = f"在第 {game.day} 天達成目標，最終資金: ${game.money}"
                color = GOLD
            else:
                msg1 = "遊戲結束：破產且無可用帳號"
                msg2 = "你的水軍帝國已經瓦解..."
                color = RED
            
            screen.blit(title_font.render(msg1, True, color), (WINDOW_WIDTH//2 - 200, 300))
            screen.blit(font.render(msg2, True, WHITE), (WINDOW_WIDTH//2 - 180, 360))
            screen.blit(font.render("請關閉視窗重新開始", True, (150, 150, 150)), (WINDOW_WIDTH//2 - 100, 420))

        # 3. 更新螢幕
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
