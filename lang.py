# -*- coding: utf-8 -*-
import argparse
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog

# 设置日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

INCLUDE_CSS = False
LOAD_CRACK = False
CRACK_ONLY = False


def run_command(cmd, shell=False):
    """运行命令并处理异常。"""
    logging.info(f"Running command: {cmd}")
    try:
        subprocess.run(cmd, shell=shell, check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed with error: {e}")
        sys.exit(1)
    except FileNotFoundError:
        logging.error(f"Command not found: {cmd}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error running command: {cmd} - {e}")
        sys.exit(1)


def read_file(file_path, strip_empty=True):
    """读取文件内容并处理异常。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            if strip_empty:
                return [line.rstrip("\r\n") for line in file if line.strip()]
            return file.read()
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading file: {file_path} - {e}")
        sys.exit(1)


def search_in_files(modifier, search_terms):
    """在文件中搜索字符串并打印结果。"""

    # 根据全局变量是否包含 CSS 文件
    code_files = modifier.get_code_files()
    app_path = f"{modifier.termius_path}/app"

    if not os.path.exists(app_path):
        modifier.decompress_asar()

    found_files = []
    for file_path in code_files:
        file_content = read_file(file_path, strip_empty=False)
        if file_content and all(term in file_content for term in search_terms):
            found_files.append(file_path)

    if found_files:
        logging.info(f"Found all terms {search_terms} in: {found_files}")
    else:
        logging.info(f"No results found for terms {search_terms}.")


class TermiusModifier:
    def __init__(self, termius_path):
        self.termius_path = termius_path
        self.files_cache = {}
        self.cn_lang = []

    def load_cn_lang(self, lang_file="locales.txt"):
        """加载语言文件内容到 cn_lang 中。"""
        if not CRACK_ONLY:
            self.cn_lang = read_file(lang_file)
            if not self.cn_lang:
                logging.error("Failed to load language file.")
                sys.exit(1)

        if LOAD_CRACK or CRACK_ONLY:
            crack_content = read_file("crack.txt", strip_empty=False)
            if crack_content:
                self.cn_lang.extend(crack_content.splitlines())
            else:
                logging.error("Failed to load crack file.")

    def decompress_asar(self):
        cmd = f"asar extract {self.termius_path}/app.asar {self.termius_path}/app"
        run_command(cmd, shell=True)

    def pack_to_asar(self):
        cmd = f'asar pack {self.termius_path}/app {self.termius_path}/app.asar --unpack-dir {{"node_modules/@termius,out"}}'
        run_command(cmd, shell=True)

    def backup_asar(self):
        """备份 app.asar 文件。"""
        backup_path = f"{self.termius_path}/app.asar.bak"
        if not os.path.exists(backup_path):
            shutil.copy(f"{self.termius_path}/app.asar", backup_path)
        else:
            shutil.copy(backup_path, f"{self.termius_path}/app.asar")

    def load_files(self, code_files):
        """加载文件内容到缓存中。"""
        for file in code_files:
            if os.path.exists(file):
                self.files_cache[file] = read_file(file, strip_empty=False)

    def replace_strings_in_content(self, file_content):
        """在内容中替换字符串。"""
        if not file_content:
            return file_content

        for lang in self.cn_lang:
            if lang.startswith("#"):
                continue
            if "|" in lang:
                old_value, new_value = lang.split("|", 1)
                if old_value.startswith('/') and old_value.endswith('/') and not old_value.startswith('//') and not old_value.endswith('//'):
                    regex = re.compile(old_value[1:-1])
                    file_content = regex.sub(new_value, file_content)
                else:
                    file_content = file_content.replace(old_value, new_value)
            else:
                logging.error(f"Skipping invalid entry: {lang}")

        return file_content

    def replace_strings_in_files(self):
        """在文件中替换字符串。"""
        for file_path in self.files_cache:
            self.files_cache[file_path] = self.replace_strings_in_content(self.files_cache[file_path])

    def write_files(self):
        """将修改后的内容写入文件。"""
        for file_path, content in self.files_cache.items():
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(content)

    def get_code_files(self):
        """获取所有代码文件路径（包含 .code 和可选的 .css 文件）。"""
        prefix_links = [
            os.path.join(self.termius_path, 'app', 'background-process', 'assets'),
            os.path.join(self.termius_path, 'app', 'ui-process', 'assets'),
            os.path.join(self.termius_path, 'app', 'main-process'),
        ]
        code_files = []
        for prefix in prefix_links:
            for root, _, files in os.walk(prefix):
                if INCLUDE_CSS:
                    code_files.extend([os.path.join(root, f) for f in files if f.endswith(('.js', '.css'))])
                else:
                    code_files.extend([os.path.join(root, f) for f in files if f.endswith(".js")])
        return code_files

    def perform_replacement(self):
        """执行字符串替换的所有步骤。"""
        self.backup_asar()
        app_path = f"{self.termius_path}/app"
        if os.path.exists(app_path):
            shutil.rmtree(app_path)

        if not os.path.exists(app_path):
            self.decompress_asar()

        self.load_cn_lang()
        code_files = self.get_code_files()

        self.load_files(code_files)
        self.replace_strings_in_files()
        self.write_files()
        self.pack_to_asar()
        logging.info("Replacement done.")


def is_valid_path(path):
    """验证路径是否合法"""
    return path and os.path.isdir(path)


def is_asar_exists(path):
    """检查指定路径下是否存在 app.asar 文件"""
    return os.path.exists(os.path.join(path, 'app.asar'))


def select_directory(title):
    """弹出文件夹选择对话框，让用户手动文件夹路径。"""
    try:
        root = tk.Tk()
        root.withdraw()
        selected_path = filedialog.askdirectory(title=title)
        root.destroy()
        return selected_path if is_valid_path(selected_path) else None
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        sys.exit(1)


def get_termius_path():
    """获取 Termius 的路径。"""
    default_paths = {
        'Windows': lambda: os.path.join(os.getenv('USERPROFILE'), 'AppData', 'Local', 'Programs', 'Termius', 'resources'),
        'Darwin': lambda: '/Applications/Termius.app/Contents/Resources',
        'Linux': lambda: '/opt/Termius/resources'
    }
    system = platform.system()
    path_generator = default_paths.get(system)

    if path_generator:
        termius_path = path_generator()  # 调用 lambda 函数生成路径
    else:
        raise NotImplementedError(f"不支持的操作系统: {system}")
    if not is_asar_exists(termius_path):
        logging.error(f"Termius app.asar file not found at: {os.path.join(termius_path, 'app.asar')}")
        logging.info("Please select the correct Termius folder.")
        termius_path = select_directory("请选择包含 app.asar 的 Termius 路径")
        if not termius_path or not is_asar_exists(termius_path):
            logging.error("Valid Termius app.asar file not found. Exiting.")
            sys.exit(1)

    return termius_path


def check_asar_installed():
    """检查是否安装了 asar 命令。"""
    run_command("asar --version", shell=True)


def main():
    parser = argparse.ArgumentParser(description='Modify Termius application.')
    parser.add_argument('-search', '-S', nargs='+', help="Search for terms in JS and CSS files.")
    parser.add_argument('-replace', '-R', action='store_true', help='Perform replacement using lang.txt.')
    parser.add_argument('-css', '-C', action='store_true', help='Include CSS files in search and replacement.')
    parser.add_argument('-crack', '-K', action='store_true', help='Load crack.txt file.')
    parser.add_argument('-crackonly', '-O', action='store_true', help='Load crack.txt file only(Do not execute translate).')
    args = parser.parse_args()

    global INCLUDE_CSS, LOAD_CRACK, CRACK_ONLY
    INCLUDE_CSS = args.css
    LOAD_CRACK = args.crack
    CRACK_ONLY = args.crackonly

    check_asar_installed()

    termius_path = get_termius_path()

    modifier = TermiusModifier(termius_path)

    # 如果没有提供 `-search` ， `-replace` 以及`-crackonly`参数，默认执行 `-replace`
    if not (args.replace or args.search or args.crackonly):
        args.replace = True

    if args.replace or args.crackonly:
        modifier.perform_replacement()
    elif args.search:
        search_in_files(modifier, args.search)
    else:
        logging.error("Invalid command. Use '-search' or '-replace'.")


if __name__ == "__main__":
    main()
