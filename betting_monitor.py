import requests
import time
import json
from datetime import datetime
from bs4 import BeautifulSoup
import logging
from typing import Dict, List, Set
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BettingMonitor:
    def __init__(self, config_file: str = 'config.json'):
        """Inicializa o monitor com configurações"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Carrega configurações
        self.config = self.load_config(config_file)
        
        # Armazena jogos já notificados para evitar spam
        self.notified_games = set()
        
    def load_config(self, config_file: str) -> Dict:
        """Carrega configurações do arquivo JSON"""
        default_config = {
            "monitored_categories": ["lol", "counter_strike"],
            "notification_methods": {
                "email": {
                    "enabled": False,
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "email_user": "",
                    "email_password": "",
                    "recipient": ""
                },
                "telegram": {
                    "enabled": True,
                    "bot_token": "7515363058:AAH_snuawhCciTdxJZFhfR4TV_fTk1WlHrg",
                    "chat_id": "7638499009"
                }
            },
            "check_interval": 300,  # 5 minutos
            "duelbits_enabled": True,
            "pinnacle_enabled": True
        }
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Mescla com configurações padrão
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        except FileNotFoundError:
            logging.info(f"Arquivo {config_file} não encontrado. Criando com configurações padrão...")
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            return default_config

    def filter_lol_games(self, containers, soup_content: str) -> List:
        """Filtra jogos de LoL por ligas específicas"""
        lol_leagues = [
            # Tier 1
            'LTA Norte', 'LTA Norte', 'LTA Sul', 'LEC EMEA', 'LCK', 'LPL', 'LCP',
            # Tier 2
            'EMEA Masters', 'TCL', 'LVP', 'Prime League', 'Ultraliga', 'VCS', 'LJL', 'PCS',
            # Torneios
            'Worlds', 'MSI', 'First Stand', 'World Championship', 'Mid-Season Invitational'
        ]
        
        filtered_games = []
        for container in containers:
            game_text = container.get_text().lower()
            # Verifica se menciona alguma liga específica do LoL
            if any(league.lower() in game_text for league in lol_leagues) or \
               any(keyword in game_text for keyword in ['league of legends', 'lol', 'rift']):
                filtered_games.append(container)
        
        return filtered_games
    
    def filter_cs_games(self, containers, soup_content: str) -> List:
        """Filtra jogos de CS por ligas/torneios específicos"""
        cs_tournaments = [
            # Tier S
            'PGL Major', 'BLAST Premier', 'IEM', 'Intel Extreme Masters',
            # Tier 1  
            'ESL Pro League', 'ESL Pro Tour', 'PGL',
            # Tier 2
            'ESL Challenger', 'FACEiT', 'ESEA', 'Qualifier'
        ]
        
        filtered_games = []
        for container in containers:
            game_text = container.get_text().lower()
            # Verifica se menciona algum torneio específico do CS
            if any(tournament.lower() in game_text for tournament in cs_tournaments) or \
               any(keyword in game_text for keyword in ['counter-strike', 'cs2', 'cs:go']):
                filtered_games.append(container)
        
        return filtered_games

    def identify_lol_league(self, game_text: str) -> str:
        """Identifica a liga específica do LoL baseado no texto"""
        text_lower = game_text.lower()
        
        # Tier 1
        if any(x in text_lower for x in ['lta norte', 'lta north', 'americas north']):
            return '🏆 LTA Norte'
        elif any(x in text_lower for x in ['lta sul', 'lta south', 'americas south']):
            return '🏆 LTA Sul' 
        elif any(x in text_lower for x in ['lec', 'emea']):
            return '🏆 LEC EMEA'
        elif 'lck' in text_lower:
            return '🏆 LCK'
        elif 'lpl' in text_lower:
            return '🏆 LPL'
        elif any(x in text_lower for x in ['lcp', 'pacific']):
            return '🏆 LCP'
        
        # Tier 2
        elif any(x in text_lower for x in ['emea masters', 'masters emea']):
            return '🥈 EMEA Masters'
        elif 'tcl' in text_lower:
            return '🥈 TCL'
        elif 'lvp' in text_lower:
            return '🥈 LVP'
        elif any(x in text_lower for x in ['prime league', 'primeleague']):
            return '🥈 Prime League'
        elif 'ultraliga' in text_lower:
            return '🥈 Ultraliga'
        elif 'vcs' in text_lower:
            return '🥈 VCS'
        elif 'ljl' in text_lower:
            return '🥈 LJL'
        elif 'pcs' in text_lower:
            return '🥈 PCS'
        
        # Torneios
        elif any(x in text_lower for x in ['worlds', 'world championship']):
            return '🌍 Worlds'
        elif any(x in text_lower for x in ['msi', 'mid-season']):
            return '🌍 MSI'
        elif 'first stand' in text_lower:
            return '🌍 First Stand'
        
        return '🎮 LoL - Liga não identificada'
    
    def identify_cs_tournament(self, game_text: str) -> str:
        """Identifica o torneio específico do CS baseado no texto"""
        text_lower = game_text.lower()
        
        # Tier S
        if any(x in text_lower for x in ['pgl major', 'major championship']):
            return '👑 PGL Major'
        elif any(x in text_lower for x in ['blast premier', 'blast pro']):
            return '👑 BLAST Premier'
        elif any(x in text_lower for x in ['iem', 'intel extreme masters']):
            return '👑 IEM'
        
        # Tier 1
        elif any(x in text_lower for x in ['esl pro league', 'pro league']):
            return '🏆 ESL Pro League'
        elif any(x in text_lower for x in ['esl pro tour', 'pro tour']):
            return '🏆 ESL Pro Tour'
        elif 'pgl' in text_lower and 'major' not in text_lower:
            return '🏆 PGL Tournament'
        
        # Tier 2
        elif any(x in text_lower for x in ['esl challenger', 'challenger league']):
            return '🥈 ESL Challenger'
        elif 'faceit' in text_lower:
            return '🥈 FACEiT'
        elif 'esea' in text_lower:
            return '🥈 ESEA'
        elif any(x in text_lower for x in ['qualifier', 'qualif']):
            return '🥈 Qualifier'
        
        return '🔫 CS - Torneio não identificado'

    def scrape_duelbits(self) -> List[Dict]:
        """Scraping da DuelBits"""
        try:
            games = []
            
            # URLs específicas para LoL e CS na DuelBits
            sport_urls = {
                'lol': 'https://duelbits.com/esports/league-of-legends',
                'counter_strike': 'https://duelbits.com/esports/counter-strike'
            }
            
            # URLs backup caso as específicas não existam
            esports_backup_urls = [
                'https://duelbits.com/esports',
                'https://duelbits.com/sports/esports',
                'https://duelbits.com/esports/lol',
                'https://duelbits.com/esports/cs2'
            ]
            
            for category, url in sport_urls.items():
                if category not in self.config['monitored_categories']:
                    continue
                    
                try:
                    response = self.session.get(url, timeout=10)
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # DuelBits pode usar estrutura diferente, procura por containers típicos
                    game_containers = soup.find_all('div', class_=['match-card', 'event-item', 'game-row', 'match-row', 'esports-event'])
                    
                    # Se não encontrou na URL específica, tenta na URL geral de esports
                    if not game_containers and category in ['lol', 'counter_strike']:
                        for backup_url in esports_backup_urls:
                            try:
                                backup_response = self.session.get(backup_url, timeout=10)
                                backup_soup = BeautifulSoup(backup_response.content, 'html.parser')
                                all_containers = backup_soup.find_all('div', class_=['match-card', 'event-item', 'game-row', 'match-row', 'esports-event'])
                                
                                # Filtra por game específico se encontrar containers
                                if all_containers:
                                    if category == 'lol':
                                        game_containers = self.filter_lol_games(all_containers, backup_response.text)
                                    elif category == 'counter_strike':
                                        game_containers = self.filter_cs_games(all_containers, backup_response.text)
                                    
                                    if game_containers:
                                        break
                            except:
                                continue
                    
                    for container in game_containers:
                        try:
                            # Extrai informações do jogo + identifica liga específica
                            teams_elem = container.find('div', class_=['teams', 'match-teams', 'participants', 'competitors'])
                            odds_elem = container.find('div', class_=['odds', 'match-odds', 'prices', 'betting-odds'])
                            time_elem = container.find('div', class_=['time', 'match-time', 'start-time', 'event-time'])
                            league_elem = container.find('div', class_=['league', 'tournament', 'competition', 'event-league'])
                            
                            if teams_elem and odds_elem:
                                teams = teams_elem.get_text(strip=True)
                                odds = odds_elem.get_text(strip=True)
                                match_time = time_elem.get_text(strip=True) if time_elem else "N/A"
                                league = league_elem.get_text(strip=True) if league_elem else "Liga não identificada"
                                
                                # Identifica a liga específica baseada no texto
                                if category == 'lol':
                                    league = self.identify_lol_league(container.get_text())
                                elif category == 'counter_strike':
                                    league = self.identify_cs_tournament(container.get_text())
                                
                                game_id = f"duelbits_{category}_{hash(teams + match_time + league)}"
                                
                                if game_id not in self.notified_games:
                                    games.append({
                                        'id': game_id,
                                        'platform': 'DuelBits',
                                        'category': category,
                                        'teams': teams,
                                        'odds': odds,
                                        'time': match_time,
                                        'league': league,
                                        'url': url
                                    })
                                    
                        except Exception as e:
                            logging.error(f"Erro ao processar jogo individual na DuelBits: {e}")
                            continue
                    
                    time.sleep(1)  # Rate limiting
                    
                except Exception as e:
                    logging.error(f"Erro ao scraping DuelBits categoria {category}: {e}")
                    continue
                    
            return games
            
        except Exception as e:
            logging.error(f"Erro geral no scraping da DuelBits: {e}")
            return []

    def scrape_pinnacle(self) -> List[Dict]:
        """Scraping da Pinnacle"""
        try:
            games = []
            
            # URLs para diferentes esportes na Pinnacle
            sport_urls = {
                'lol': 'https://www.pinnacle.com/en/esports/league-of-legends',
                'counter_strike': 'https://www.pinnacle.com/en/esports/counter-strike'
            }
            
            for category, url in sport_urls.items():
                if category not in self.config['monitored_categories']:
                    continue
                    
                try:
                    response = self.session.get(url, timeout=10)
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Pinnacle tem estrutura diferente, procura por elementos específicos
                    game_containers = soup.find_all('div', class_=['event', 'match', 'game-row'])
                    
                    for container in game_containers:
                        try:
                            # Extrai informações do jogo
                            teams_elem = container.find('span', class_=['participants', 'teams'])
                            odds_elems = container.find_all('span', class_=['price', 'odd'])
                            time_elem = container.find('span', class_=['start-time', 'time'])
                            
                            if teams_elem and odds_elems:
                                teams = teams_elem.get_text(strip=True)
                                odds = ' | '.join([odd.get_text(strip=True) for odd in odds_elems])
                                match_time = time_elem.get_text(strip=True) if time_elem else "N/A"
                                
                                # Identifica a liga específica baseada no texto
                                if category == 'lol':
                                    league = self.identify_lol_league(container.get_text())
                                elif category == 'counter_strike':
                                    league = self.identify_cs_tournament(container.get_text())
                                else:
                                    league = "Liga não identificada"
                                
                                game_id = f"pinnacle_{category}_{hash(teams + match_time)}"
                                
                                if game_id not in self.notified_games:
                                    games.append({
                                        'id': game_id,
                                        'platform': 'Pinnacle',
                                        'category': category,
                                        'teams': teams,
                                        'odds': odds,
                                        'time': match_time,
                                        'league': league,
                                        'url': url
                                    })
                                    
                        except Exception as e:
                            logging.error(f"Erro ao processar jogo individual na Pinnacle: {e}")
                            continue
                    
                    time.sleep(1)  # Rate limiting
                    
                except Exception as e:
                    logging.error(f"Erro ao scraping Pinnacle categoria {category}: {e}")
                    continue
                    
            return games
            
        except Exception as e:
            logging.error(f"Erro geral no scraping da Pinnacle: {e}")
            return []

    def send_email_notification(self, games: List[Dict]):
        """Envia notificação por email"""
        if not self.config['notification_methods']['email']['enabled']:
            return
            
        try:
            email_config = self.config['notification_methods']['email']
            
            msg = MIMEMultipart()
            msg['From'] = email_config['email_user']
            msg['To'] = email_config['recipient']
            msg['Subject'] = f"🚨 Novos jogos encontrados - {datetime.now().strftime('%H:%M')}"
            
            body = "Novos jogos disponíveis para apostas:\n\n"
            
            for game in games:
                body += f"🎮 {game['platform']} - {game['category'].upper()}\n"
                body += f"🏟️ {game['league']}\n"
                body += f"⚡ {game['teams']}\n"
                body += f"💰 Odds: {game['odds']}\n"
                body += f"⏰ Horário: {game['time']}\n"
                body += f"🔗 Link: {game['url']}\n"
                body += "-" * 50 + "\n\n"
                
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
            server.starttls()
            server.login(email_config['email_user'], email_config['email_password'])
            server.send_message(msg)
            server.quit()
            
            logging.info(f"Email enviado com {len(games)} novos jogos")
            
        except Exception as e:
            logging.error(f"Erro ao enviar email: {e}")

    def send_telegram_notification(self, games: List[Dict]):
        """Envia notificação via Telegram"""
        if not self.config['notification_methods']['telegram']['enabled']:
            return
            
        try:
            telegram_config = self.config['notification_methods']['telegram']
            
            message = f"🚨 *Novos jogos encontrados* - {datetime.now().strftime('%H:%M')}\n\n"
            
            for game in games:
                message += f"🎮 *{game['platform']}* - {game['category'].upper()}\n"
                message += f"🏟️ {game['league']}\n"
                message += f"⚡ {game['teams']}\n"
                message += f"💰 Odds: `{game['odds']}`\n"
                message += f"⏰ Horário: {game['time']}\n"
                message += f"🔗 [Apostar]({game['url']})\n"
                message += "➖➖➖➖➖➖➖➖➖➖\n\n"
            
            url = f"https://api.telegram.org/bot{telegram_config['bot_token']}/sendMessage"
            data = {
                'chat_id': telegram_config['chat_id'],
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                logging.info(f"Telegram enviado com {len(games)} novos jogos")
            else:
                logging.error(f"Erro ao enviar Telegram: {response.text}")
                
        except Exception as e:
            logging.error(f"Erro ao enviar Telegram: {e}")

    def notify_new_games(self, games: List[Dict]):
        """Envia notificações sobre novos jogos"""
        if not games:
            return
            
        logging.info(f"Enviando notificações para {len(games)} novos jogos")
        
        # Envia por todos os métodos habilitados
        self.send_email_notification(games)
        self.send_telegram_notification(games)
        
        # Marca jogos como notificados
        for game in games:
            self.notified_games.add(game['id'])

    def run_monitoring_cycle(self):
        """Executa um ciclo de monitoramento"""
        logging.info("Iniciando ciclo de monitoramento...")
        
        all_new_games = []
        
        # Scraping da DuelBits
        if self.config.get('duelbits_enabled', True):
            logging.info("Fazendo scraping da DuelBits...")
            duelbits_games = self.scrape_duelbits()
            all_new_games.extend(duelbits_games)
            
        # Scraping da Pinnacle  
        if self.config.get('pinnacle_enabled', True):
            logging.info("Fazendo scraping da Pinnacle...")
            pinnacle_games = self.scrape_pinnacle()
            all_new_games.extend(pinnacle_games)
            
        # Notifica sobre novos jogos
        if all_new_games:
            logging.info(f"Encontrados {len(all_new_games)} novos jogos!")
            self.notify_new_games(all_new_games)
        else:
            logging.info("Nenhum jogo novo encontrado neste ciclo")

    def start_monitoring(self):
        """Inicia o monitoramento contínuo"""
        logging.info("🤖 Bot de monitoramento iniciado!")
        logging.info(f"📊 Categorias monitoradas: {self.config['monitored_categories']}")
        logging.info(f"⏰ Intervalo de verificação: {self.config['check_interval']} segundos")
        
        while True:
            try:
                self.run_monitoring_cycle()
                
                # Aguarda antes do próximo ciclo
                logging.info(f"💤 Aguardando {self.config['check_interval']} segundos...")
                time.sleep(self.config['check_interval'])
                
            except KeyboardInterrupt:
                logging.info("🛑 Monitoramento interrompido pelo usuário")
                break
            except Exception as e:
                logging.error(f"Erro no ciclo de monitoramento: {e}")
                logging.info("Aguardando 60 segundos antes de tentar novamente...")
                time.sleep(60)

def main():
    """Função principal"""
    print("🚀 Inicializando Bot Monitor de Apostas...")
    print("📋 Plataformas: DuelBits e Pinnacle")
    print("⚙️ Carregando configurações...")
    
    try:
        monitor = BettingMonitor()
        monitor.start_monitoring()
    except Exception as e:
        logging.error(f"Erro fatal: {e}")
        print(f"❌ Erro ao inicializar o bot: {e}")

if __name__ == "__main__":
    main()