from tronpy import Tron
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider
import os
import sys
import time
import requests
from datetime import datetime

class TronTransferBot:
    def __init__(self, master_private_key, slave_address, network="mainnet", api_key=None):
        """
        Инициализация бота для разового перевода TRX
        """
        # Обновленный список рабочих узлов TRON
        self.alternative_nodes = [
            "https://api.trongrid.io",
            "https://api.tronstack.io",
            "https://api.shasta.trongrid.io" if network == "testnet" else "https://api.trongrid.io",
            "https://tron-rpc.publicnode.com",
            "https://tron.mytokenpocket.vip"
        ]
        self.api_key = api_key
        self.network = network

        # Настройка ключей и адресов
        self.master_private_key = PrivateKey(bytes.fromhex(master_private_key))
        self.master_address = self.master_private_key.public_key.to_base58check_address()
        self.slave_address = slave_address

        print(f"👤 Master: {self.master_address}")
        print(f"👤 Slave: {self.slave_address}")

    def create_client_with_api_key(self, node_url):
        """Создание клиента с поддержкой API ключа для TronGrid"""
        try:
            if self.api_key and "trongrid" in node_url:
                # Для TronGrid используем специальный подход с API ключом
                client = Tron(HTTPProvider(node_url))
                # Устанавливаем API ключ в провайдере вручную
                if hasattr(client._client, 'session'):
                    client._client.session.headers.update({"TRON-PRO-API-KEY": self.api_key})
                elif hasattr(client._client.provider, 'session'):
                    client._client.provider.session.headers.update({"TRON-PRO-API-KEY": self.api_key})
                return client
            else:
                return Tron(HTTPProvider(node_url))
        except Exception as e:
            print(f"❌ Ошибка создания клиента для {node_url}: {e}")
            return None

    def test_node_connectivity(self, node_url):
        """Проверка доступности узла"""
        try:
            response = requests.get(f"{node_url}/wallet/getnodeinfo", timeout=10)
            return response.status_code == 200
        except:
            return False

    def get_trx_balance(self, address):
        """Получить баланс TRX для указанного адреса, пробуя альтернативные узлы"""
        for node in self.alternative_nodes:
            try:
                print(f"🔄 Проверка доступности {node}...")
                if not self.test_node_connectivity(node):
                    print(f"⚠️ Узел {node} недоступен, пропускаем...")
                    continue
                
                print(f"🔄 Получение баланса с {node}...")
                client = self.create_client_with_api_key(node)
                if client is None:
                    continue
                    
                account = client.get_account(address)
                balance_sun = account.get('balance', 0)
                balance_trx = balance_sun / 1_000_000
                print(f"✅ Успешно получен баланс с {node}")
                return balance_trx
            except Exception as e:
                print(f"❌ Ошибка с {node}: {e}")
        
        print(f"❌ Не удалось получить баланс на всех узлах")
        return None

    def transfer_trx(self, slave_balance):
        """Перевод TRX со slave на master аккаунт (оставляем 0.81 TRX)"""
        try:
            amount_to_transfer = slave_balance - 0.81

            if amount_to_transfer <= 0:
                print(f"❌ Недостаточно средств для перевода (баланс: {slave_balance:.6f} TRX)")
                return False, None

            print(f"💸 Перевод {amount_to_transfer:.6f} TRX (оставляем 0.81 TRX на балансе)...")

            # Для транзакций также используем первый рабочий узел
            for node in self.alternative_nodes:
                try:
                    print(f"🔄 Попытка отправки через {node}...")
                    if not self.test_node_connectivity(node):
                        print(f"⚠️ Узел {node} недоступен для транзакций, пропускаем...")
                        continue
                    
                    client = self.create_client_with_api_key(node)
                    if client is None:
                        continue
                    
                    # Создаем транзакцию
                    transaction = client.trx.transfer(
                        from_=self.slave_address,
                        to=self.master_address,
                        amount=int(amount_to_transfer * 1_000_000)
                    ).build()
                    
                    # Подписываем транзакцию
                    signed_transaction = transaction.sign(self.master_private_key)
                    
                    # Отправляем транзакцию
                    result = signed_transaction.broadcast()
                    
                    if result and 'txid' in result:
                        print(f"✅ Транзакция успешна!")
                        print(f"📊 Переведено: {amount_to_transfer:.6f} TRX")
                        print(f"🔗 TXID: {result['txid']}")
                        print(f"🌐 https://tronscan.org/#/transaction/{result['txid']}")
                        return True, result['txid']
                    else:
                        print(f"❌ Неожиданный результат транзакции: {result}")
                        continue
                        
                except Exception as e:
                    print(f"❌ Ошибка отправки с {node}: {e}")
                    continue
            
            print(f"❌ Не удалось выполнить транзакцию ни на одном узле")
            return False, None

        except Exception as e:
            print(f"❌ Исключение при переводе: {e}")
            return False, None

    def check_and_transfer(self):
        """Проверить баланс и выполнить перевод если нужно"""
        print(f"🚀 Запуск проверки - {datetime.now()}")
        print("=" * 50)

        # Проверяем баланс slave аккаунта
        slave_balance = self.get_trx_balance(self.slave_address)

        if slave_balance is None:
            print("❌ Не удалось получить баланс slave аккаунта")
            return False

        print(f"💰 Баланс slave: {slave_balance:.6f} TRX")

        # Если баланс больше 2 TRX (чтобы можно было оставить 0.81), выполняем перевод
        if slave_balance > 2.0:
            transfer_amount = slave_balance - 0.81
            print(f"🎯 Баланс позволяет перевод {transfer_amount:.6f} TRX (оставляем 0.81 TRX)")

            success, txid = self.transfer_trx(slave_balance)
            if success:
                print(f"🎉 Перевод выполнен успешно!")

                # Получаем обновленный баланс
                print("⏳ Ожидание подтверждения транзакции...")
                time.sleep(5)  # Увеличиваем время ожидания
                new_balance = self.get_trx_balance(self.slave_address)
                if new_balance is not None:
                    print(f"📊 Новый баланс slave: {new_balance:.6f} TRX")

                return True
            else:
                print(f"💥 Ошибка при переводе")
                return False
        else:
            print(f"⏱️ Баланс недостаточен для перевода (нужно > 2 TRX, чтобы оставить 0.81)")
            return True

def main():
    """Основная функция для разового запуска"""

    # Получаем конфигурацию из переменных окружения
    MASTER_PRIVATE_KEY = os.getenv('MASTER_PRIVATE_KEY')
    SLAVE_ADDRESS = os.getenv('SLAVE_ADDRESS')
    NETWORK = os.getenv('NETWORK', 'mainnet')
    API_KEY = os.getenv('API_KEY')

    # Проверка обязательных параметров
    if not MASTER_PRIVATE_KEY:
        print("❌ ОШИБКА: Не задана переменная MASTER_PRIVATE_KEY")
        sys.exit(1)

    if not SLAVE_ADDRESS:
        print("❌ ОШИБКА: Не задана переменная SLAVE_ADDRESS")
        sys.exit(1)

    if len(MASTER_PRIVATE_KEY) != 64:
        print("❌ ОШИБКА: Неверный формат приватного ключа")
        sys.exit(1)

    try:
        # Создаем и запускаем бота
        bot = TronTransferBot(MASTER_PRIVATE_KEY, SLAVE_ADDRESS, NETWORK, API_KEY)
        success = bot.check_and_transfer()

        print("=" * 50)
        if success:
            print("✅ Операция завершена успешно")
            sys.exit(0)
        else:
            print("❌ Операция завершена с ошибками")
            sys.exit(1)

    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
