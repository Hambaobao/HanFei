from multiprocessing import Pool
from pathlib import Path

import logging
import openai
import json
import time
import numpy as np

openai.api_key = "sk-iUeKahIIV2L7JM5AyKXTT3BlbkFJ******************"


def set_logger(seed_id):
    logFormatter = logging.basicConfig(format='%(asctime)s - %(levelname)s - %(name)s -   %(message)s', datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)
    logger = logging.getLogger()

    path = Path("logs")
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    path /= Path('seed-' + str(seed_id).zfill(2) + '.log')

    fileHandler = logging.FileHandler(path, mode='w')
    fileHandler.setFormatter(logFormatter)
    logger.addHandler(fileHandler)

    return logger


def get_multi_seeds(fold_id, num_folds=20, path='multi_seeds/multi_seeds.tsv'):
    # 读取multi_seeds.tsv文件，将种子词分成num_folds份，返回第fold_id份
    multi_seeds_path = Path(path)
    if not multi_seeds_path.exists():
        print("multi_seeds.tsv文件不存在！")
        return None

    with open(multi_seeds_path, 'r', encoding="utf8") as f:
        seeds = f.readlines()

    # 将seeds分成num_folds份
    seeds = np.array(seeds)
    seeds = np.array_split(seeds, num_folds)

    return seeds[fold_id]


def do_get_response(messages, temperature):
    while True:
        try:
            response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages, temperature=temperature)
            break
        except openai.error.OpenAIError:
            time.sleep(3)
            continue
    content = response.choices[0].message.content
    return content


def get_lawyer_response(history, topic, temperature=0.1):
    messages = []
    prompt = "以下是一位用户与律师之间的对话，用户在向律师咨询" + f"\"{topic}\"" + "有关的问题。你将扮演这位律师的角色，请尽可能详细的回答用户的问题。\n\n"
    messages.append({"role": "system", "content": prompt})
    for h in history:
        messages.append({"role": 'user' if h["role"] == 'assitant' else 'assistant', "content": h["content"]})

    content = do_get_response(messages, temperature)
    messages.append({"role": 'assitant', "content": content})

    return content, messages


def get_user_response(history, topic, temperature=0.1):
    messages = []
    prompt = "以下是一位用户与律师之间的对话，用户在向律师咨询" + f"\"{topic}\"" + "有关的问题。你将扮演这位用户的角色，继续向律师更详细地咨询你不了解的问题，经过多轮交流之后，你才能以很小的概率回复\"谢谢您的解答，再见。\"。\n\n"
    messages.append({"role": "system", "content": prompt})
    for h in history:
        messages.append({"role": 'user' if h["role"] == 'assitant' else 'assistant', "content": h["content"]})

    content = do_get_response(messages, temperature)
    messages.append({"role": 'assitant', "content": content})

    return content, messages


def save_conversation(seed_id, messages):
    # 将messages写入json文件
    dest_dir = Path('conversations')
    if not dest_dir.exists():
        dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / Path('seed-' + str(seed_id).zfill(2) + '.json')
    with open(dest_path, 'w', encoding="utf8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=4)


def generate_conversation(seed_id, max_turns=10, max_history=4):
    logger = set_logger(seed_id)
    topic = seeds[seed_id].strip()

    #  模拟发起对话
    conversation = []
    history = [{'role': 'assistant', 'content': seeds[seed_id].strip()}]
    conversation.append({'role': 'user', 'content': seeds[seed_id].strip()})

    logger.info("User: {}".format(seeds[seed_id].strip()))
    flag = False
    for k in range(max_turns):
        logger.info("Turn: " + str(k))

        if len(history) > max_history:
            history = history[-max_history:]

        lawyer_response, _ = get_lawyer_response(history, topic, temperature=0.2)
        logger.info("Lawyer: {}".format(lawyer_response))
        history.append({"role": 'assistant', "content": lawyer_response})
        conversation.append({"role": 'assistant', "content": lawyer_response})

        if len(history) > max_history:
            history = history[-max_history:]

        user_response, _ = get_user_response(history, topic, temperature=0.2)
        logger.info("User: {}".format(user_response))
        history.append({"role": 'user', "content": user_response})
        conversation.append({"role": 'user', "content": user_response})

        if "再见" in user_response:
            flag = True
            break

    if not flag:
        conversation = conversation[:-1]
        conversation.append({"role": 'user', "content": "非常感谢您的解答，再见。"})
    save_conversation(seed_id, conversation)


seeds = get_multi_seeds(fold_id=0)

if __name__ == '__main__':
    num_seeds = len(seeds)

    # 并发调用 generate_conversation 函数，生成多个对话
    pool = Pool(processes=8)
    pool.map(generate_conversation, range(num_seeds))
    pool.close()
    pool.join()