import requests
import hashlib
import binascii
import json
import random
import socket
import time
import sys
import logging
from colorama import init, Fore, Style
from telegram import Bot
from telegram.error import TelegramError
import asyncio

# Initialize colorama
init(autoreset=True)

# Set your Bitcoin address and Telegram token/chat_id
address = "177k1GxsiZbSfuhwq5s7WniL8a28hQnkZc"  # <----- TROQUE AQUI ANTES DE EXECUTAR O CODIGO
telegram_token = ""
chat_id = ""  

# Initialize current block height
current_height = 0
interrupted = False  # Flag to handle Ctrl+C interruption

nerd = '''    
     ███╗   ██╗███████╗██████╗ ██████╗                           
     ████╗  ██║██╔════╝██╔══██╗██╔══██╗                          
     ██╔██╗ ██║█████╗  ██████╔╝██║  ██║                          
     ██║╚██╗██║██╔══╝  ██╔══██╗██║  ██║                          
     ██║ ╚████║███████╗██║  ██║██████╔╝                          
     ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═════╝                           
'''
miner = '''                                                               
     ███╗   ███╗██╗███╗   ██╗███████╗██████╗     ██████╗  ██████╗
     ████╗ ████║██║████╗  ██║██╔════╝██╔══██╗    ██╔══██╗██╔════╝
     ██╔████╔██║██║██╔██╗ ██║█████╗  ██████╔╝    ██████╔╝██║     
     ██║╚██╔╝██║██║██║╚██╗██║██╔══╝  ██╔══██╗    ██╔═══╝ ██║     
     ██║ ╚═╝ ██║██║██║ ╚████║███████╗██║  ██║    ██║     ╚██████╗
     ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝    ╚═╝      ╚═════╝                                                                                               
'''

def print_ascii_art():
    try:
        print(Fore.YELLOW + nerd + Style.RESET_ALL)
        print(Fore.WHITE + miner + Style.RESET_ALL)
    except UnicodeEncodeError as e:
        print("Não foi possível exibir a arte ASCII devido a uma falha na codificação:", e)

def delay_print(message, delay=0.1):
    """Imprime uma mensagem com um pequeno atraso entre cada caractere."""
    for char in message:
        print(char, end='', flush=True)
        time.sleep(delay)
    print()

async def send_telegram_message(message):
    try:
        bot = Bot(token=telegram_token)
        await bot.send_message(chat_id=chat_id, text=message)
    except TelegramError as e:
        log(f'Erro ao enviar mensagem para o Telegram: {e}')

def log(msg):
    logging.info(msg)

# Initialize logging
logging.basicConfig(level=logging.INFO, filename="miner.log", format='%(asctime)s %(message)s', force=True)

print_ascii_art()

entry_address = input(f'{Fore.MAGENTA}[*]{Fore.RESET}{Fore.BLUE} DIGITE A SUA CARTEIRA BITCOIN : {Fore.RESET} ')
address = str(entry_address)
print(f'\n{Fore.YELLOW}ENDEREÇO DA CARTEIRA {Fore.RESET} ===>> {Fore.MAGENTA}{address}{Style.RESET_ALL}')
print(f"{Fore.YELLOW}{'-' * 66}{Style.RESET_ALL}")

delay_print('Iniciando a Mineração...')
print(f"\n{Fore.YELLOW}{'-' * 66}{Style.RESET_ALL}")

time.sleep(3)

def get_current_block_height():
    try:
        r = requests.get('https://blockchain.info/latestblock')
        return int(r.json()['height'])
    except Exception as e:
        log(f'Erro ao obter altura do bloco: {e}')
        return 0

async def BitcoinMiner(restart=False):
    global interrupted

    if restart:
        await asyncio.sleep(2)
        log('[*] Bitcoin Miner Restarted')
        await send_telegram_message('Bitcoin Miner Restarted')
    else:
        log('[*] Bitcoin Miner Started')
        await send_telegram_message('Bitcoin Miner Started')

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('solo.ckpool.org', 3333))

    sock.sendall(b'{"id": 1, "method": "mining.subscribe", "params": []}\n')

    lines = sock.recv(1024).decode().split('\n')

    response = json.loads(lines[0])
    subscription_details, extranonce1, extranonce2_size = response['result']

    sock.sendall(b'{"params": ["' + address.encode() + b'", "password"], "id": 2, "method": "mining.authorize"}\n')

    response = b''
    while response.count(b'\n') < 4 and not (b'mining.notify' in response):
        response += sock.recv(1024)

    responses = [json.loads(res) for res in response.decode().split('\n') if len(res.strip()) > 0 and 'mining.notify' in res]
    job_id, prevhash, coinbase1, coinbase2, merkle_branch, version, nbits, ntime, clean_jobs = responses[0]['params']
    target = (nbits[2:] + '00' * (int(nbits[:2], 16) - 3)).zfill(64)
    extranonce2 = hex(random.randint(0, 2 ** 32 - 1))[2:].zfill(2 * extranonce2_size)

    coinbase = coinbase1 + extranonce1 + extranonce2 + coinbase2
    coinbase_hash_bin = hashlib.sha256(hashlib.sha256(binascii.unhexlify(coinbase)).digest()).digest()

    merkle_root = coinbase_hash_bin
    for h in merkle_branch:
        merkle_root = hashlib.sha256(hashlib.sha256(merkle_root + binascii.unhexlify(h)).digest()).digest()

    merkle_root = binascii.hexlify(merkle_root).decode()

    merkle_root = ''.join([merkle_root[i] + merkle_root[i + 1] for i in range(0, len(merkle_root), 2)][::-1])

    current_work = get_current_block_height()
    print(f'\n{Fore.YELLOW}BLOCO ATUAL = {Style.RESET_ALL} {current_work}')
    print(f'{Fore.BLUE}ALVO ATUAL = {Style.RESET_ALL} {target}')
    z = 0
    verified_hashes = 0
    start_time = time.time()  # Start timing

    while not interrupted:
        if current_height > current_work:
            log('[*] Reiniciando')
            await BitcoinMiner(restart=True)
            break

        try:
            nonce = hex(random.randint(0, 2 ** 32 - 1))[2:].zfill(8)
            block_header = version + prevhash + merkle_root + nbits + ntime + nonce + \
                           '000000800000000000000000000000000000000000000000000000000000000000000000000000000000000080020000'
            hash = hashlib.sha256(hashlib.sha256(binascii.unhexlify(block_header)).digest()).digest()
            hash = binascii.hexlify(hash).decode()

            verified_hashes += 1
            if verified_hashes % 1000 == 0:
                elapsed_time = time.time() - start_time
                if elapsed_time > 0:
                    hash_rate = verified_hashes / elapsed_time
                    hash_rate_str = f'{hash_rate:.2f} H/s' if hash_rate < 1000 else f'{hash_rate/1000:.2f} MH/s'
                    sys.stdout.write(f'\r{Fore.GREEN}{hash_rate_str} - {verified_hashes} - HASH : 000000000000000000000{hash}{Style.RESET_ALL}')
                    sys.stdout.flush()

            if hash.startswith('000000000000000000000'):
                log('hash: {}'.format(hash))
                z += 1
                await send_telegram_message(f'Novo hash encontrado:\n{hash}')

            if hash.startswith('000000000000000'):
                log('hash: {}'.format(hash))
                z += 1
                await send_telegram_message(f'Novo hash encontrado:\n{hash}')
                   
            if hash.startswith('000000000000000'):
                log('hash: {}'.format(hash))
                z += 1
                await send_telegram_message(f'Novo hash encontrado:\n{hash}')

            if hash.startswith('000000000000'):
                log('hash: {}'.format(hash))
                z += 1
                await send_telegram_message(f'Novo hash encontrado:\n{hash}')

            if hash.startswith('0000000'):
                log('hash: {}'.format(hash))
                z += 1
                await send_telegram_message(f'Novo hash encontrado:\n{hash}')

            if hash < target:
                print(f'{Fore.GREEN}[*] BLOCO MINERADO!!{Style.RESET_ALL}')
                log('[*] success!!')
                log(block_header)
                log(f'hash: {hash}')

                message = (
                    f'Bloco Minerado!\n'
                    f'Hash: {hash}\n'
                    f'Block Header: {block_header}\n'
                    f'Job ID: {job_id}\n'
                    f'Extranonce2: {extranonce2}\n'
                    f'Ntime: {ntime}\n'
                    f'Nonce: {nonce}'
                )
                await send_telegram_message(message)

                payload = bytes(
                    '{"params": ["' + address + '", "' + job_id + '", "' + extranonce2 \
                    + '", "' + ntime + '", "' + nonce + '"], "id": 1, "method": "mining.submit"}\n', 'utf-8')
                sock.sendall(payload)
                log(payload.decode())
                ret = sock.recv(1024)
                log(ret.decode())

                return True

        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}[*] Mineração interrompida pelo o usuário.{Style.RESET_ALL}")
            interrupted = True
            await send_telegram_message('Mineração interrompida pelo usuário.')

async def newBlockListener():
    global current_height, interrupted

    last_height = current_height  # Guarda a altura do bloco inicial

    while not interrupted:
        try:
            r = requests.get('https://blockchain.info/latestblock')
            new_height = int(r.json()['height'])

            # Se a altura do bloco mudou, envie uma mensagem
            if new_height != last_height:
                message = f'Altura do Bloco Atualizada!\nNova Altura: {new_height}'
                await send_telegram_message(message)
                last_height = new_height  # Atualiza a altura do bloco conhecida

            current_height = new_height
            await asyncio.sleep(5)
        except Exception as e:
            log(f'Erro ao obter altura do bloco: {e}')
            await asyncio.sleep(5)

    log('[*] Block listener interrupted.')

async def main():
    log('[*] Starting Bitcoin Miner...')
    log('[*] Current Bitcoin Address: ' + address)
    await send_telegram_message('Bitcoin Miner Started. Current Bitcoin Address: ' + address)

    tasks = [
        asyncio.create_task(newBlockListener()),
        asyncio.create_task(BitcoinMiner())
    ]

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        global interrupted
        interrupted = True
        log('[*] Interrupt signal received. Shutting down...')
        await send_telegram_message('Interrupt signal received. Shutting down...')
        print(f"\n{Fore.YELLOW}[*] Mineração interrompida pelo o usuário.{Style.RESET_ALL}")

if __name__ == '__main__':
    asyncio.run(main())
