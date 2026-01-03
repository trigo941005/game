import pygame
import random
import sys
import pickle
import os
import time

# --- 遊戲設定與常數 ---
WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 768
FPS = 60

# 顏色定義 (R, G, B)
WHITE = (200, 255, 200) # 駭客風：帶綠色的白
BLACK = (0, 0, 0)
BG_COLOR = (0, 10, 0)         # 駭客風：深黑綠背景
PANEL_COLOR = (0, 30, 0)      # 駭客風：深綠區塊
BUTTON_COLOR = (0, 60, 0)     # 駭客風：暗綠按鈕
BUTTON_HOVER = (0, 180, 0)    # 駭客風：亮綠懸停
TEXT_COLOR = (0, 255, 0)      # 駭客風：終端機綠
GREEN = (0, 255, 0)
RED = (255, 50, 50)
GOLD = (255, 215, 0)

# --- 路徑設定 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- 全域設定 ---
class GameSettings:
    def __init__(self):
        self.volume = 0.5

SETTINGS = GameSettings()
screen = None # 全域螢幕變數

def update_volume(vol):
    SETTINGS.volume = max(0.0, min(1.0, vol))
    try:
        pygame.mixer.music.set_volume(SETTINGS.volume)
        for s in SOUNDS.values():
            s.set_volume(SETTINGS.volume)
    except:
        pass

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
        pygame.mixer.music.set_volume(SETTINGS.volume)
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
        'lose': 'lose.wav',
        'hover': 'hover.mp3' # 新增懸停音效
    }
    for name, filename in sfx_files.items():
        try:
            SOUNDS[name] = pygame.mixer.Sound(filename)
            SOUNDS[name].set_volume(SETTINGS.volume)
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

class FloatingText:
    """浮動文字特效"""
    def __init__(self, x, y, text, color):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.timer = 60  # 持續 60 frames (約 1 秒)

    def update(self):
        self.y -= 1  # 向上飄移
        self.timer -= 1

    def draw(self, surface, font):
        if self.timer > 0:
            # 隨著時間稍微變透明的效果在 Pygame 比較複雜，這裡簡單處理位置移動
            surf = font.render(self.text, True, self.color)
            surface.blit(surf, (self.x, self.y))

class GameState:
    """管理遊戲數據與邏輯"""
    def __init__(self, difficulty="Standard"):
        self.difficulty = difficulty
        if difficulty == "Easy":
            self.money = 2000
            self.base_risk_modifier = 0.7
            self.target_reputation = 3000
            self.salary_per_bot = 20 # 簡單模式工資
        elif difficulty == "Hard":
            self.money = 500
            self.base_risk_modifier = 1.3
            self.target_reputation = 10000
            self.salary_per_bot = 80 # 困難模式工資
        else:
            self.money = 1000
            self.base_risk_modifier = 1.0
            self.target_reputation = 5000
            self.salary_per_bot = 50 # 普通模式工資

        self.risk_modifier = self.base_risk_modifier
        self.bots = [Bot() for _ in range(5)]
        self.available_missions = []
        self.day = 1
        self.reputation = 0
        self.pending_money = 0 # 待結算資金 (隔日入帳)
        self.selected_mission = None # 當前選中的任務（等待選擇策略）
        self.deploy_count = 0 # 準備派出的帳號數量
        self.game_over = False
        self.victory = False
        self.bankruptcy_days = 0 # 破產倒數計數器
        self.current_filename = None # 追蹤當前存檔檔名
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

        self.floating_texts = [] # 視覺特效列表

        self.generate_missions()

    def log(self, message):
        """新增訊息到日誌視窗"""
        self.logs.append(message)
        if len(self.logs) > 20: # 只保留最近 20 條訊息
            self.logs.pop(0)

    def add_float_text(self, x, y, text, color):
        """新增浮動文字"""
        self.floating_texts.append(FloatingText(x, y, text, color))

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
        
        # 失敗條件：連續 3 天資金為負 (破產)
        if self.bankruptcy_days >= 3:
            self.game_over = True
            self.victory = False
            play_sound('lose')
            
            # 破產刪檔機制
            if self.current_filename:
                try:
                    target_file = os.path.join(BASE_DIR, self.current_filename)
                    if os.path.exists(target_file):
                        os.remove(target_file)
                        self.log(f"公司破產！已刪除紀錄: {self.current_filename}")
                except Exception as e:
                    print(f"刪除失敗: {e}")

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
            self.add_float_text(100, 650, f"-${cost}", RED)
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
            self.add_float_text(pygame.mouse.get_pos()[0], pygame.mouse.get_pos()[1], f"-${cost}", RED)
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
            self.add_float_text(300, 650, f"-${total_cost}", RED)
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
            self.add_float_text(400, 300, f"+${mission.reward} (待入帳)", GOLD)
            self.add_float_text(400, 330, f"+{mission.difficulty} 聲望", GREEN)
            play_sound('success')
            self.trigger_ban_wave(mission.difficulty * risk_factor)
        else:
            self.reputation = max(0, self.reputation - 2)
            self.log("任務失敗！影響力不足。")
            self.add_float_text(400, 300, "任務失敗", RED)
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
            self.add_float_text(WINDOW_WIDTH//2, WINDOW_HEIGHT//2, f"損失 {banned_count} 帳號!", RED)
            play_sound('alert')
        self.check_status()
        self.check_achievements()

    def next_day(self):
        self.day += 1
        
        # 結算昨日收益
        if self.pending_money > 0:
            self.money += self.pending_money
            self.log(f"昨日收益 ${self.pending_money} 已入帳")
            self.add_float_text(150, 50, f"+${self.pending_money}", GOLD)
            play_sound('cash')
            self.pending_money = 0

        # 清理被封鎖的帳號
        for b in self.bots:
            b.reset_daily()
        original_count = len(self.bots)
        self.bots = [b for b in self.bots if not b.is_banned]
        removed = original_count - len(self.bots)
        
        # 支付每日工資
        salary_cost = len(self.bots) * self.salary_per_bot
        if salary_cost > 0:
            self.money -= salary_cost
            self.log(f"支付工資: ${salary_cost} (${self.salary_per_bot}/人)")
            self.add_float_text(150, 80, f"-${salary_cost} (工資)", RED)

        # 檢查是否破產 (資金為負)
        if self.money < 0:
            self.bankruptcy_days += 1
            self.log(f"⚠ 資金赤字！破產倒數: {self.bankruptcy_days}/3")
            play_sound('alert')
        else:
            self.bankruptcy_days = 0

        # 重置風險值並觸發隨機事件
        self.risk_modifier = self.base_risk_modifier
        self.trigger_random_event()

        self.generate_missions()
        self.log(f"=== 第 {self.day} 天 ===")
        if removed > 0:
            self.log(f"昨日共有 {removed} 個帳號被永久封鎖。")
        self.check_status()
        self.check_achievements()
        
        # 自動存檔
        if not self.game_over:
            self.save_game("autosave.pkl")

    def trigger_random_event(self):
        """觸發每日隨機事件"""
        if random.random() < 0.3: # 30% 機率觸發
            events = [
                ("平台演算法更新", "今日風險係數加倍！", lambda: setattr(self, 'risk_modifier', self.risk_modifier * 2.0)),
                ("加密貨幣暴漲", "獲得額外資金 $300", lambda: setattr(self, 'money', self.money + 300)),
                ("網軍醜聞曝光", "聲望下降 50 點", lambda: setattr(self, 'reputation', max(0, self.reputation - 50))),
                ("黑客工具流出", "今日風險係數減半", lambda: setattr(self, 'risk_modifier', self.risk_modifier * 0.5)),
            ]
            name, desc, effect = random.choice(events)
            effect()
            self.log(f"【隨機事件】{name}: {desc}")
            self.add_float_text(WINDOW_WIDTH//2, 200, f"事件: {name}", (255, 100, 255))
            play_sound('alert')

    def save_game(self, filename='savegame.pkl'):
        """儲存遊戲狀態"""
        if not filename.endswith('.pkl'):
            filename += '.pkl'
        self.current_filename = filename # 更新當前檔名
        filepath = os.path.join(BASE_DIR, filename)
        data = {
            'money': self.money,
            'pending_money': self.pending_money,
            'bots': self.bots,
            'available_missions': self.available_missions,
            'day': self.day,
            'reputation': self.reputation,
            'difficulty': self.difficulty,
            'base_risk_modifier': self.base_risk_modifier,
            'target_reputation': self.target_reputation,
            'logs': self.logs,
            'unlocked_achievements': [a.key for a in self.achievements if a.unlocked],
            'bankruptcy_days': self.bankruptcy_days,
            'current_filename': self.current_filename
        }
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)
            self.log(f"遊戲進度已儲存至 {filename}")
        except Exception as e:
            self.log(f"儲存失敗: {e}")

    def load_game(self, filename):
        """讀取遊戲狀態"""
        filepath = os.path.join(BASE_DIR, filename)
        if not os.path.exists(filepath):
            self.log("檔案不存在。")
            return

        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            # 更新當前物件屬性
            self.__dict__.update(data)
            self.current_filename = filename # 確保讀取後更新當前檔名
            
            # 資料遷移：確保舊存檔的機器人有新屬性
            for b in self.bots:
                if not hasattr(b, 'max_uses'):
                    b.max_uses = 1 + (b.level // 2)
                if not hasattr(b, 'used_today'):
                    b.used_today = 0
                b.influence = b.level * 25 # 更新數值平衡
            if not hasattr(self, 'pending_money'):
                self.pending_money = 0
            if not hasattr(self, 'base_risk_modifier'):
                self.base_risk_modifier = self.risk_modifier
            if not hasattr(self, 'floating_texts'):
                self.floating_texts = []
            if not hasattr(self, 'salary_per_bot'):
                if self.difficulty == "Easy": self.salary_per_bot = 20
                elif self.difficulty == "Hard": self.salary_per_bot = 80
                else: self.salary_per_bot = 50
            if not hasattr(self, 'bankruptcy_days'):
                self.bankruptcy_days = 0

            # 恢復成就狀態
            if hasattr(self, 'unlocked_achievements'):
                for ach in self.achievements:
                    if ach.key in self.unlocked_achievements:
                        ach.unlocked = True

            # 重置暫時狀態 (避免讀檔後介面卡住)
            self.selected_mission = None
            self.game_over = False
            self.victory = False
            
            self.log(f"已讀取: {filename}")
        except Exception as e:
            self.log(f"讀取失敗: {e}")

# --- UI 輔助類別 ---

class Button:
    def __init__(self, x, y, w, h, text, callback):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.callback = callback
        self.color = BUTTON_COLOR
        self.hovered = False

    def draw(self, surface, font):
        mouse_pos = pygame.mouse.get_pos()
        is_hovering = self.rect.collidepoint(mouse_pos)
        
        # 懸停音效邏輯
        if is_hovering and not self.hovered:
            play_sound('hover')
        self.hovered = is_hovering

        # 滑鼠懸停變色效果
        current_color = BUTTON_HOVER if is_hovering else self.color
        text_color = BLACK if is_hovering else TEXT_COLOR # 懸停時文字變黑，背景變亮
        
        pygame.draw.rect(surface, BLACK, self.rect) # 黑色底
        pygame.draw.rect(surface, current_color, self.rect, 2) # 綠色框 (駭客風不填充)
        if is_hovering:
             pygame.draw.rect(surface, current_color, self.rect) # 懸停時填充
        
        text_surf = font.render(self.text, True, text_color)
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
                pygame.draw.rect(screen, BUTTON_COLOR, btn_rect)
                pygame.draw.rect(screen, TEXT_COLOR, btn_rect, 1)
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

def save_load_screen(screen, game, font, title_font, is_save_mode=False):
    """存檔/讀檔選擇介面 (支援翻頁)"""
    clock = pygame.time.Clock()
    running = True
    page = 0
    items_per_page = 8
    loaded_game_obj = None
    
    btn_back = Button(50, 700, 100, 50, "返回", lambda: None)
    
    def open_save_folder():
        try:
            os.startfile(BASE_DIR)
        except Exception:
            pass
    btn_open_folder = Button(380, 700, 200, 50, "開啟存檔資料夾", open_save_folder)

    # 如果是存檔模式，增加一個新建存檔按鈕
    btn_new_save = None
    if is_save_mode:
        btn_new_save = Button(170, 700, 200, 50, "新建存檔", lambda: None)

    # --- 預先讀取檔案資訊 (避免每幀讀取) ---
    def get_files_info():
        info_list = []
        try:
            f_names = [f for f in os.listdir(BASE_DIR) if f.endswith('.pkl')]
            # 按時間排序
            f_names.sort(key=lambda x: os.path.getmtime(os.path.join(BASE_DIR, x)), reverse=True)
            
            for fname in f_names:
                fpath = os.path.join(BASE_DIR, fname)
                mtime = time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(fpath)))
                day = "?"
                money = "?"
                try:
                    with open(fpath, 'rb') as f:
                        data = pickle.load(f)
                        if isinstance(data, dict):
                            day = data.get('day', '?')
                            money = data.get('money', '?')
                except:
                    pass
                info_list.append({
                    'name': fname,
                    'mtime': mtime,
                    'day': day,
                    'money': money
                })
        except Exception:
            pass
        return info_list

    files_info = get_files_info()

    while running:
        screen.fill(BG_COLOR)
        
        title_text = "選擇存檔位置 (覆蓋)" if is_save_mode else "選擇讀取進度"
        screen.blit(title_font.render(title_text, True, GOLD), (50, 30))

        total_pages = max(1, (len(files_info) - 1) // items_per_page + 1)
        if page >= total_pages: page = max(0, total_pages - 1)

        # 顯示列表
        start = page * items_per_page
        end = min(start + items_per_page, len(files_info))
        
        y = 100
        for i in range(start, end):
            info = files_info[i]
            fname = info['name']
            
            display_name = fname
            if fname == "autosave.pkl":
                display_name = "自動存檔 (autosave)"
            if i == 0: # 最新的檔案
                display_name += " [最新]"
            
            # 繪製選項背景
            row_rect = pygame.Rect(50, y, 900, 50)
            bg_color = PANEL_COLOR
            if row_rect.collidepoint(pygame.mouse.get_pos()):
                bg_color = (70, 70, 70)
            pygame.draw.rect(screen, bg_color, row_rect, 1) # 改為線框
            
            screen.blit(font.render(display_name, True, WHITE), (70, y + 10))
            
            # 顯示天數與資金
            stats_text = f"第 {info['day']} 天 | ${info['money']}"
            screen.blit(font.render(stats_text, True, GOLD), (400, y + 10))
            
            screen.blit(font.render(info['mtime'], True, (150, 150, 150)), (620, y + 10))

            # 刪除按鈕
            del_rect = pygame.Rect(850, y + 10, 80, 30)
            del_color = RED if del_rect.collidepoint(pygame.mouse.get_pos()) else (180, 50, 50)
            pygame.draw.rect(screen, del_color, del_rect)
            screen.blit(font.render("刪除", True, WHITE), (865, y + 12))
            
            y += 60

        # 頁碼
        page_str = f"頁數: {page+1}/{total_pages}"
        screen.blit(font.render(page_str, True, WHITE), (850, 40))
        
        # 翻頁按鈕區域
        prev_rect = pygame.Rect(810, 40, 30, 30)
        next_rect = pygame.Rect(980, 40, 30, 30)
        pygame.draw.polygon(screen, WHITE, [(830, 45), (830, 65), (810, 55)])
        pygame.draw.polygon(screen, WHITE, [(980, 45), (980, 65), (1000, 55)])

        btn_back.draw(screen, font)
        btn_open_folder.draw(screen, font)
        if btn_new_save:
            btn_new_save.draw(screen, font)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if btn_back.rect.collidepoint(event.pos):
                    running = False
                    play_sound('click')
                
                if btn_open_folder.rect.collidepoint(event.pos):
                    play_sound('click')
                    btn_open_folder.callback()
                
                if btn_new_save and btn_new_save.rect.collidepoint(event.pos):
                    # 新建存檔
                    # 使用可讀性更高的時間格式 (YYYYMMDD_HHMMSS)，並防止檔名重複
                    timestamp = time.strftime('%Y%m%d_%H%M%S')
                    base_name = f"save_{timestamp}"
                    new_name = f"{base_name}.pkl"
                    
                    # 檢查檔案是否存在，若存在則加上流水號
                    counter = 1
                    while os.path.exists(os.path.join(BASE_DIR, new_name)):
                        new_name = f"{base_name}_{counter}.pkl"
                        counter += 1

                    game.save_game(new_name)
                    running = False
                    play_sound('success')

                # 翻頁
                if prev_rect.collidepoint(event.pos) and page > 0: page -= 1; play_sound('click')
                if next_rect.collidepoint(event.pos) and page < total_pages - 1: page += 1; play_sound('click')

                # 點擊檔案
                y_check = 100
                for i in range(start, end):
                    # 檢查刪除按鈕
                    del_check_rect = pygame.Rect(850, y_check + 10, 80, 30)
                    if del_check_rect.collidepoint(event.pos):
                        try:
                            os.remove(os.path.join(BASE_DIR, files_info[i]['name']))
                            play_sound('click')
                            # 重新讀取列表以刷新畫面
                            files_info = get_files_info()
                            total_pages = max(1, (len(files_info) - 1) // items_per_page + 1)
                            if page >= total_pages: page = max(0, total_pages - 1)
                            continue # 跳過後續點擊判斷
                        except Exception as e:
                            print(f"刪除失敗: {e}")

                    if pygame.Rect(50, y_check, 900, 50).collidepoint(event.pos):
                        fname = files_info[i]['name']
                        if is_save_mode:
                            if game: game.save_game(fname)
                            play_sound('success')
                        else:
                            if game:
                                game.load_game(fname)
                            else:
                                # 主選單讀取模式：建立臨時遊戲狀態來讀取
                                temp_game = GameState("Standard")
                                temp_game.load_game(fname)
                                loaded_game_obj = temp_game
                            play_sound('success')
                        running = False
                    y_check += 60
        clock.tick(FPS)
    return loaded_game_obj

def settings_screen(game, font, title_font):
    """設定頁面"""
    clock = pygame.time.Clock()
    running = True
    
    btn_back = Button(50, 700, 100, 50, "返回", lambda: None)

    while running:
        screen.fill(BG_COLOR)
        screen.blit(title_font.render("遊戲設定", True, GOLD), (50, 30))

        # --- 音量控制 ---
        screen.blit(font.render(f"音量: {int(SETTINGS.volume * 100)}%", True, WHITE), (100, 150))
        # 滑桿背景
        bar_rect = pygame.Rect(250, 160, 400, 10)
        pygame.draw.rect(screen, (0, 50, 0), bar_rect)
        # 滑桿進度
        fill_width = int(SETTINGS.volume * 400)
        pygame.draw.rect(screen, GREEN, (250, 160, fill_width, 10))
        # 滑桿按鈕
        knob_x = 250 + fill_width
        pygame.draw.circle(screen, WHITE, (knob_x, 165), 12)

        btn_back.draw(screen, font)
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if btn_back.rect.collidepoint(event.pos):
                    running = False
                    play_sound('click')

            # 滑鼠拖曳或點擊調整音量
            if pygame.mouse.get_pressed()[0]:
                mx, my = pygame.mouse.get_pos()
                if 230 <= mx <= 670 and 140 <= my <= 190:
                    ratio = (mx - 250) / 400
                    update_volume(ratio)

        clock.tick(FPS)

def main():
    global screen
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("網路水軍模擬器 v0.2 (Pygame Edition)")
    init_audio() # 初始化音效系統
    clock = pygame.time.Clock()
    
    # 設定字型
    font = get_chinese_font()
    title_font = pygame.font.Font(pygame.font.match_font(["microsoftjhenghei", "simhei"]), 36)

    # --- 難度選擇畫面 ---
    game = None
    
    def start_new_game(d):
        nonlocal game
        game = GameState(d)
        play_sound('click')

    cx = WINDOW_WIDTH // 2 - 150
    btn_easy = Button(cx, 300, 300, 50, "簡單 (資金$2000 / 風險低)", lambda: start_new_game("Easy"))
    btn_standard = Button(cx, 370, 300, 50, "標準 (資金$1000 / 標準)", lambda: start_new_game("Standard"))
    btn_hard = Button(cx, 440, 300, 50, "困難 (資金$500 / 風險高)", lambda: start_new_game("Hard"))

    def open_load_menu():
        nonlocal game
        loaded = save_load_screen(screen, None, font, title_font, False)
        if loaded:
            game = loaded

    btn_load_save = Button(cx, 510, 300, 50, "讀取存檔", open_load_menu)

    # 尋找最新的存檔 (繼續遊戲功能)
    btn_continue = None
    save_files = [f for f in os.listdir(BASE_DIR) if f.endswith('.pkl')]
    if save_files:
        latest_save = max(save_files, key=lambda x: os.path.getmtime(os.path.join(BASE_DIR, x)))
        mtime = time.strftime('%m/%d %H:%M', time.localtime(os.path.getmtime(os.path.join(BASE_DIR, latest_save))))
        
        def load_latest():
            nonlocal game
            try:
                g = GameState("Standard") # 建立臨時狀態
                g.load_game(latest_save)  # 讀取存檔覆蓋
                game = g
                play_sound('click')
            except Exception as e:
                print(f"讀取失敗: {e}")

        btn_continue = Button(cx, 230, 300, 50, f"繼續遊戲 ({mtime})", load_latest)

    while game is None:
        screen.fill(BG_COLOR)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            if btn_continue:
                btn_continue.check_click(event)
            btn_easy.check_click(event)
            btn_standard.check_click(event)
            btn_hard.check_click(event)
            btn_load_save.check_click(event)
        
        title_surf = title_font.render("網路水軍模擬器", True, GOLD)
        screen.blit(title_surf, (WINDOW_WIDTH//2 - title_surf.get_width()//2, 150))
        
        if btn_continue:
            btn_continue.draw(screen, font)
        btn_easy.draw(screen, font)
        btn_standard.draw(screen, font)
        btn_hard.draw(screen, font)
        btn_load_save.draw(screen, font)
        
        pygame.display.flip()
        clock.tick(FPS)

    # 建立按鈕
    btn_buy_1 = Button(50, 680, 105, 50, "買1 ($100)", lambda: game.buy_bot(1))
    btn_buy_5 = Button(165, 680, 105, 50, "買5 ($500)", lambda: game.buy_bot(5))
    btn_next = Button(280, 680, 200, 50, "休息一天 (刷新)", game.next_day)
    btn_load = Button(500, 680, 100, 50, "讀檔", lambda: save_load_screen(screen, game, font, title_font, False))
    btn_manage = Button(620, 680, 150, 50, "帳號管理", lambda: account_management_screen(screen, game, font, title_font))
    btn_settings = Button(790, 680, 100, 50, "設定", lambda: settings_screen(game, font, title_font))

    # --- 策略選擇介面按鈕 ---
    # 調整數量按鈕
    def adjust_deploy(delta):
        available = len([b for b in game.bots if b.is_available()])
        new_count = game.deploy_count + delta
        if 1 <= new_count <= available:
            game.deploy_count = new_count
            play_sound('click')

    btn_dec = Button(700, 280, 50, 40, "-", lambda: adjust_deploy(-1))
    btn_inc = Button(860, 280, 50, 40, "+", lambda: adjust_deploy(1))

    def run_strat(s):
        if game.selected_mission:
            game.execute_mission(game.selected_mission, s, game.deploy_count)
            game.selected_mission = None

    # 調整策略按鈕位置 (往下移以容納數量選擇器)
    btn_strat_spam = Button(630, 330, 360, 50, "暴力洗版 (影響力+++ / 風險高)", lambda: run_strat("spam"))
    btn_strat_norm = Button(630, 390, 360, 50, "一般帶風向 (標準)", lambda: run_strat("normal"))
    btn_strat_troll = Button(630, 450, 360, 50, "反串釣魚 (影響力- / 風險低)", lambda: run_strat("troll"))
    btn_cancel = Button(630, 520, 360, 50, "取消", lambda: setattr(game, 'selected_mission', None))

    log_scroll_offset = 0 # 日誌捲動位置 (0 = 最底部)
    running = True
    while running:
        # 1. 事件處理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            # 處理滑鼠滾輪 (日誌捲動)
            if event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if pygame.Rect(680, 110, 300, 550).collidepoint(mx, my):
                    log_scroll_offset += event.y

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
                btn_load.check_click(event)
                btn_manage.check_click(event)
                btn_settings.check_click(event)

                # 處理任務列表的點擊
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    # 檢查是否點擊了任務區域
                    for i, mission in enumerate(game.available_missions):
                        mission_rect = pygame.Rect(50, 140 + i * 75, 550, 70)
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
                    start_x, start_y = 50, 580
                    box_size, gap = 15, 5
                    for idx, bot in enumerate(game.bots):
                        bx = start_x + (idx % 30) * (box_size + gap)
                        by = start_y + (idx // 30) * (box_size + gap)
                        if pygame.Rect(bx, by, box_size, box_size).collidepoint(mx, my):
                            play_sound('click')
                            game.upgrade_bot(bot)

        # 2.5 更新邏輯
        # 更新浮動文字
        for ft in game.floating_texts:
            ft.update()
        game.floating_texts = [ft for ft in game.floating_texts if ft.timer > 0]

        # 2. 畫面繪製
        screen.fill(BG_COLOR)

        # 繪製背景網格 (駭客風)
        for x in range(0, WINDOW_WIDTH, 40):
            pygame.draw.line(screen, (0, 30, 0), (x, 0), (x, WINDOW_HEIGHT), 1)
        for y in range(0, WINDOW_HEIGHT, 40):
            pygame.draw.line(screen, (0, 30, 0), (0, y), (WINDOW_WIDTH, y), 1)

        # --- 頂部資訊欄 ---
        header_text = f"第 {game.day} 天 | 資金: ${game.money} (+${game.pending_money}) | 聲望: {game.reputation}/{game.target_reputation} | 帳號: {len(game.bots)}"
        header_surf = title_font.render(header_text, True, GOLD)
        screen.blit(header_surf, (50, 30))

        # 顯示破產倒數警告
        if game.bankruptcy_days > 0:
            warn_text = f"⚠ 破產倒數: {3 - game.bankruptcy_days} 天"
            warn_surf = title_font.render(warn_text, True, RED)
            screen.blit(warn_surf, (50, 70))

        # --- 左側：任務列表 ---
        screen.blit(font.render("可用任務 (點擊執行):", True, WHITE), (50, 110))
        
        for i, mission in enumerate(game.available_missions):
            rect = pygame.Rect(50, 140 + i * 75, 550, 70)
            
            # 任務滑鼠懸停效果
            color = PANEL_COLOR
            if rect.collidepoint(pygame.mouse.get_pos()):
                color = (70, 70, 70)
            
            pygame.draw.rect(screen, BLACK, rect) # 黑底
            pygame.draw.rect(screen, TEXT_COLOR, rect, 1) # 綠框
            
            # 任務文字
            info_text = f"{mission.name}"
            detail_text = f"難度: {mission.difficulty} | 報酬: ${mission.reward} | 需求影響力: {mission.required_influence}"
            
            screen.blit(font.render(info_text, True, GREEN), (rect.x + 10, rect.y + 10))
            screen.blit(font.render(detail_text, True, TEXT_COLOR), (rect.x + 10, rect.y + 35))

        # --- 左側下方：帳號可視化 ---
        viz_y = 520
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
        start_x, start_y = 50, viz_y + 60 # y=580
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
        pygame.draw.rect(screen, TEXT_COLOR, log_bg, 1) # 綠色邊框
        
        screen.blit(font.render("系統日誌:", True, WHITE), (680, 80))
        
        # 自動換行處理
        wrapped_lines = []
        max_width = 280 # 300 - 20 padding
        
        for log in game.logs:
            current_line = ""
            for char in log:
                if font.size(current_line + char)[0] <= max_width:
                    current_line += char
                else:
                    wrapped_lines.append(current_line)
                    current_line = char
            if current_line:
                wrapped_lines.append(current_line)

        # 只顯示能放入框內的最後幾行
        line_height = 30
        max_lines = 530 // line_height
        
        # 計算捲動限制
        total_lines = len(wrapped_lines)
        max_scroll = max(0, total_lines - max_lines)
        
        # 限制捲動範圍並計算切片
        if log_scroll_offset < 0: log_scroll_offset = 0
        if log_scroll_offset > max_scroll: log_scroll_offset = max_scroll

        if log_scroll_offset == 0:
            lines_to_draw = wrapped_lines[-max_lines:]
        else:
            end = total_lines - log_scroll_offset
            start = max(0, end - max_lines)
            lines_to_draw = wrapped_lines[start:end]

        log_y = 120
        for line in lines_to_draw:
            log_surf = font.render(line, True, (200, 200, 200))
            screen.blit(log_surf, (690, log_y))
            log_y += line_height

        # --- 底部：按鈕 ---
        btn_buy_1.draw(screen, font)
        btn_buy_5.draw(screen, font)
        btn_next.draw(screen, font)
        btn_load.draw(screen, font)
        btn_manage.draw(screen, font)
        btn_settings.draw(screen, font)

        # --- 繪製浮動文字 ---
        for ft in game.floating_texts:
            ft.draw(screen, font)

        # --- 策略選擇彈出視窗 (Overlay) ---
        if game.selected_mission:
            # 對話框背景 (移至右側，不覆蓋任務列表)
            dialog_rect = pygame.Rect(620, 140, 380, 500)
            pygame.draw.rect(screen, BLACK, dialog_rect)
            pygame.draw.rect(screen, TEXT_COLOR, dialog_rect, 2)
            
            # 標題與說明
            cx = dialog_rect.centerx
            screen.blit(title_font.render("選擇言論操控手段", True, GOLD), (cx - 130, 160))
            screen.blit(font.render(f"目標: {game.selected_mission.name}", True, WHITE), (640, 210))
            screen.blit(font.render("請選擇派出數量與策略：", True, (200, 200, 200)), (640, 240))
            
            # --- 數量選擇控制 ---
            # 計算預計影響力
            avail_bots = [b for b in game.bots if b.is_available()]
            avail_bots.sort(key=lambda b: b.level, reverse=True)
            selected_bots = avail_bots[:game.deploy_count]
            current_inf = sum(b.influence for b in selected_bots)

            screen.blit(font.render(f"{game.deploy_count}", True, WHITE), (770, 290))
            screen.blit(font.render(f"/ {len(avail_bots)}", True, (150, 150, 150)), (800, 290))
            screen.blit(font.render(f"預計影響力: {current_inf}", True, GOLD), (760, 255))
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
            pygame.draw.rect(screen, BLACK, notif_rect)
            pygame.draw.rect(screen, GOLD, notif_rect, 2)
            
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
            elif game.bankruptcy_days >= 3:
                msg1 = "遊戲結束：宣告破產"
                msg2 = "連續 3 天資金為負，公司倒閉..."
                color = RED
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
