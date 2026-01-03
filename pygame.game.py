import pygame
import random
import sys

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

# --- 核心邏輯類別 (與文字版類似) ---

class Bot:
    def __init__(self, level=1):
        self.level = level
        self.influence = level * 10
        self.stealth = 100 - (level * 5)
        self.is_banned = False

class Mission:
    def __init__(self, name, difficulty, reward, required_influence):
        self.name = name
        self.difficulty = difficulty
        self.reward = reward
        self.required_influence = required_influence

class GameState:
    """管理遊戲數據與邏輯"""
    def __init__(self):
        self.money = 1000
        self.bots = [Bot() for _ in range(5)]
        self.available_missions = []
        self.day = 1
        self.reputation = 0
        self.logs = ["歡迎來到《網路水軍模擬器》圖形版！", "請購買帳號或選擇任務開始。"]
        self.generate_missions()

    def log(self, message):
        """新增訊息到日誌視窗"""
        self.logs.append(message)
        if len(self.logs) > 12: # 只保留最近 12 條訊息
            self.logs.pop(0)

    def generate_missions(self):
        mission_types = [
            ("為某餐廳刷五星好評", 2, 500, 100),
            ("在論壇炒作新手機", 5, 1500, 300),
            ("攻擊競爭對手的粉專", 8, 3000, 600),
            ("洗白藝人負面新聞", 10, 8000, 1000)
        ]
        self.available_missions = []
        # 總是提供一個簡單任務
        self.available_missions.append(Mission(*mission_types[0]))
        
        # 根據聲望解鎖其他任務
        for m in mission_types:
            if self.reputation >= (m[1] * 5) - 10:
                if m[0] != mission_types[0][0]: # 避免重複
                    self.available_missions.append(Mission(*m))

    def buy_bot(self):
        cost = 100
        if self.money >= cost:
            self.money -= cost
            self.bots.append(Bot())
            self.log(f"購買成功！目前擁有 {len(self.bots)} 個帳號。")
        else:
            self.log("資金不足！需要 $100。")

    def execute_mission(self, mission):
        active_bots = [b for b in self.bots if not b.is_banned]
        total_influence = sum(b.influence for b in active_bots)
        
        self.log(f"執行: {mission.name}")
        self.log(f"影響力: {total_influence} / 需求: {mission.required_influence}")

        if total_influence >= mission.required_influence:
            self.money += mission.reward
            self.reputation += mission.difficulty
            self.log(f"任務成功！獲得報酬: ${mission.reward}")
            self.trigger_ban_wave(mission.difficulty)
        else:
            self.reputation = max(0, self.reputation - 2)
            self.log("任務失敗！影響力不足。")
            self.trigger_ban_wave(mission.difficulty // 2) # 失敗風險較低

        # 任務執行後移除
        if mission in self.available_missions:
            self.available_missions.remove(mission)

    def trigger_ban_wave(self, risk_level):
        banned_count = 0
        for bot in self.bots:
            if bot.is_banned: continue
            # 簡單的機率計算
            detection_chance = (risk_level * 5) - (bot.stealth * 0.1)
            if random.randint(0, 100) < detection_chance:
                bot.is_banned = True
                banned_count += 1
        
        if banned_count > 0:
            self.log(f"警告！平台反制，損失了 {banned_count} 個帳號！")

    def next_day(self):
        self.day += 1
        # 清理被封鎖的帳號
        original_count = len(self.bots)
        self.bots = [b for b in self.bots if not b.is_banned]
        removed = original_count - len(self.bots)
        
        self.generate_missions()
        self.log(f"=== 第 {self.day} 天 ===")
        if removed > 0:
            self.log(f"昨日共有 {removed} 個帳號被永久封鎖。")

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

def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("網路水軍模擬器 v0.2 (Pygame Edition)")
    clock = pygame.time.Clock()
    
    # 設定字型
    font = get_chinese_font()
    title_font = pygame.font.Font(pygame.font.match_font(["microsoftjhenghei", "simhei"]), 36)

    game = GameState()

    # 建立按鈕
    btn_buy = Button(50, 680, 200, 50, "購買帳號 ()", game.buy_bot)
    btn_next = Button(270, 680, 200, 50, "休息一天 (刷新)", game.next_day)

    running = True
    while running:
        # 1. 事件處理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            btn_buy.check_click(event)
            btn_next.check_click(event)

            # 處理任務列表的點擊
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                # 檢查是否點擊了任務區域
                for i, mission in enumerate(game.available_missions):
                    mission_rect = pygame.Rect(50, 150 + i * 70, 600, 60)
                    if mission_rect.collidepoint(mx, my):
                        game.execute_mission(mission)
                        break

        # 2. 畫面繪製
        screen.fill(BG_COLOR)

        # --- 頂部資訊欄 ---
        header_text = f"第 {game.day} 天  |  資金: ${game.money}  |  聲望: {game.reputation}  |  可用帳號: {len(game.bots)}"
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
        btn_buy.draw(screen, font)
        btn_next.draw(screen, font)

        # 3. 更新螢幕
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
