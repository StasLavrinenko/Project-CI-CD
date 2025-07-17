import os
import re
import glob
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import argparse
import requests

BOT_TOKEN = "7697585826:AAH3a-eMzAyoTkU9cWkqqSz0l1nFQIynAGY"
CHAT_ID = "-1002595147448"
STATS_FILE = Path("/app/logs/session_stats.json")

class LogAnalyzer:
    def __init__(self, logs_dir: str = "logs"):
        self.logs_dir = Path(logs_dir)
        self.script_start_time = datetime.now()
        self.previous_stats = self.load_previous_stats()
        self.current_stats = {}

    def load_previous_stats(self) -> Dict[str, Dict]:
        if STATS_FILE.exists():
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_current_stats(self):
        with open(STATS_FILE, 'w') as f:
            json.dump(self.current_stats, f, indent=2)

    def parse_log_line(self, line: str) -> Optional[Dict]:
        pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (.+)'
        match = re.match(pattern, line.strip())
        if not match:
            return None
        timestamp_str, message = match.groups()
        try:
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
        except ValueError:
            return None
        return {'timestamp': timestamp, 'message': message}

    def extract_session_info(self, message: str) -> Optional[Dict]:
        session_pattern = r'Session ended.*?ClientID: ([^|]+?)\s*\|.*?HasErrors: (True|False).*?StartTime: ([^|]+).*?EndTime: ([^|]+)'
        session_match = re.search(session_pattern, message)
        if session_match:
            try:
                return {
                    'client_id': session_match.group(1).strip(),
                    'has_errors': session_match.group(2) == 'True',
                    'start_time': datetime.fromisoformat(session_match.group(3).strip().replace('+00:00', '')),
                    'end_time': datetime.fromisoformat(session_match.group(4).strip().replace('+00:00', ''))
                }
            except ValueError:
                pass
        return None

    def analyze_server_logs(self, server_dir: Path) -> Dict:
        server_ip = server_dir.name
        log_files = []
        for year_dir in server_dir.iterdir():
            if year_dir.is_dir():
                log_files.extend(glob.glob(str(year_dir / "session_metrics_*.log")))
        if not log_files:
            return self._empty_result(server_ip)

        all_timestamps = []
        sessions = []
        processed_ids = set()

        for log_file in log_files:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    parsed = self.parse_log_line(line)
                    if parsed:
                        all_timestamps.append(parsed['timestamp'])
                        session = self.extract_session_info(parsed['message'])
                        if session:
                            session_id = f"{session['client_id']}-{session['start_time']}"
                            if session_id not in processed_ids:
                                sessions.append(session)
                                processed_ids.add(session_id)

        if not all_timestamps:
            return self._empty_result(server_ip)

        first_log = min(all_timestamps)
        last_log = max(all_timestamps)
        is_alive = (datetime.now(timezone.utc) - last_log.replace(tzinfo=timezone.utc)).total_seconds() < 3600
        total_sessions = len(sessions)
        error_sessions = sum(1 for s in sessions if s['has_errors'])
        error_percentage = (error_sessions / total_sessions * 100) if total_sessions else 0.0

        result = {
            'server': server_ip,
            'log_period': f"{first_log.strftime('%Y-%m-%d %H:%M:%S')} - {last_log.strftime('%Y-%m-%d %H:%M:%S')}",
            'is_alive': is_alive,
            'total_sessions': total_sessions,
            'error_sessions': error_sessions,
            'error_percentage': round(error_percentage, 2)
        }
        self.current_stats[server_ip] = {
            'total_sessions': total_sessions,
            'error_sessions': error_sessions,
            'error_percentage': round(error_percentage, 2)
        }
        return result

    def _empty_result(self, server_ip):
        self.current_stats[server_ip] = {
            'total_sessions': 0,
            'error_sessions': 0,
            'error_percentage': 0.0
        }
        return {
            'server': server_ip,
            'log_period': None,
            'is_alive': False,
            'total_sessions': 0,
            'error_sessions': 0,
            'error_percentage': 0.0
        }

    def analyze_all_servers(self) -> List[Dict]:
        if not self.logs_dir.exists():
            return []
        server_dirs = [d for d in self.logs_dir.iterdir() if d.is_dir() and re.match(r'\d+\.\d+\.\d+\.\d+', d.name)]
        return [self.analyze_server_logs(sd) for sd in sorted(server_dirs)]

    def format_results_for_telegram(self, results: List[Dict]) -> str:
        lines = ["*📊 STT Log Analysis Report*", f"_{self.script_start_time.strftime('%Y-%m-%d %H:%M:%S')}_"]
        for result in results:
            prev = self.previous_stats.get(result['server'], {})
            def delta(curr, old):
                return f"(+{curr - old})" if curr > old else f"({curr - old})" if curr < old else "(+0)"

            delta_sessions = delta(result['total_sessions'], prev.get('total_sessions', 0))
            delta_errors = delta(result['error_sessions'], prev.get('error_sessions', 0))
            delta_percent = delta(round(result['error_percentage'], 2), round(prev.get('error_percentage', 0.0), 2))

            lines.append(f"\n*{'✅' if result['is_alive'] else '❌'} SERVER: {result['server']}*")
            if result['log_period']:
                lines.append(f"  - Period: {result['log_period']}")
                lines.append(f"  - Status: {'ALIVE' if result['is_alive'] else 'OFFLINE'}")
                lines.append(f"  - Sessions: {result['total_sessions']} {delta_sessions}")
                lines.append(f"  - Errors: {result['error_sessions']} {delta_errors} ({result['error_percentage']:.2f}%) {delta_percent}")
            else:
                lines.append("  _No data available_")

        # Overall statistics
        total_servers = len(results)
        alive_servers = sum(1 for r in results if r['is_alive'])
        total_sessions = sum(r['total_sessions'] for r in results)
        total_errors = sum(r['error_sessions'] for r in results)
        
        lines.append("\n\n*📈 OVERALL STATS*")
        lines.append(f"- *Total Servers:* `{total_servers}`")
        lines.append(f"- *Alive Servers:* `{alive_servers}`")
        lines.append(f"- *Total Sessions:* `{total_sessions}`")
        lines.append(f"- *Total Errors:* `{total_errors}`")

        dead_servers = [r for r in results if not r['is_alive']]
        if dead_servers:
            mentions = "@StasLavrin @giflinn96"
            lines.append(f"\n🚨 *Warning:* {len(dead_servers)} server(s) offline!\n{mentions}")

        return '\n'.join(lines)

def send_telegram_message(message: str):
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data=payload, timeout=10)
        if response.status_code != 200:
            print("Telegram error:", response.text)
    except Exception as e:
        print("Telegram send failed:", e)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--logs-dir', default='logs')
    args = parser.parse_args()

    analyzer = LogAnalyzer(args.logs_dir)
    results = analyzer.analyze_all_servers()
    analyzer.save_current_stats()
    report = analyzer.format_results_for_telegram(results)
    send_telegram_message(report)

if __name__ == '__main__':
    main()
