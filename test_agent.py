"""
Terminalden EmlakBot'u test et — gerçek WhatsApp gerekmez.

Çalıştır:
    py test_agent.py
"""

import sys
import re
import json
from src.database.local_db import init_db, ensure_default_tenant, get_tenant, get_tenant_settings, append_message, get_recent_messages
from src.bot.agent import handle_message
from src.bot.tools import save_qualified_lead


def run_interactive_test():
    print("=== EmlakBot Terminal Testi ===")
    print("Çıkmak için 'q' yazın.\n")

    init_db()
    tid = ensure_default_tenant()
    tenant = get_tenant(tid)
    settings = get_tenant_settings(tid)
    print(f"Test tenant: {tenant['office_name']} (id={tid})\n")

    user_phone = "905551234567"
    user_name = "Yusuf"

    initial = "Siirt Merkez Lüks 3+1 Daire ilanıyla ilgileniyorum."
    print(f"[{user_name}]: {initial}")
    history = get_recent_messages(tid, user_phone, 20)
    ai_response = handle_message(initial, user_phone, tenant["office_name"], settings, history)
    print(f"\n[Bot]: {ai_response}\n")
    append_message(tid, user_phone, "user", initial)
    append_message(tid, user_phone, "assistant", ai_response)

    while True:
        try:
            user_input = input(f"[{user_name}]: ")
            if user_input.lower() in ["q", "quit", "çıkış"]:
                break
            history = get_recent_messages(tid, user_phone, 20)
            response = handle_message(user_input, user_phone, tenant["office_name"], settings, history)

            json_match = re.search(r'\{[\s\S]*"status"[\s\S]*\}', response)
            clean_response = response
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                    if data.get("status") == "QUALIFIED":
                        print(f"\n🎉 Kalifikasyon yakalandı!")
                        print(json.dumps(data, indent=2, ensure_ascii=False))
                        save_qualified_lead(
                            tenant_id=tid,
                            name=user_name,
                            phone=user_phone,
                            purpose=data.get("purpose", ""),
                            budget=data.get("budget", ""),
                            location_preference=data.get("location_preference", ""),
                            timeline=data.get("timeline", ""),
                        )
                        clean_response = response.replace(json_match.group(0), "").strip()
                except json.JSONDecodeError as e:
                    print(f"JSON çözüm hatası: {e}")

            print(f"\n[Bot]: {clean_response}\n")
            append_message(tid, user_phone, "user", user_input)
            append_message(tid, user_phone, "assistant", response)

        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    run_interactive_test()
