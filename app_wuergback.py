import os
import json
import subprocess
import platform
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import tempfile
from datetime import datetime
import logging

# Konstanten
README_CONTENT = """
This is the wuergback backup utility.
It backs up the specified directories to the configured backup directory using 7zip compression.
To configure, edit the wuergback.json file.
"""
CONFIG_FILE = "wuergback.json"
DEFAULT_LOCAL_BUFFER_DIR = os.getcwd()
DEFAULT_BACKUP_DIR_WIN = "H:\\wuergback_target"
DEFAULT_BACKUP_DIR_LINUX = "/home/austausch/wuergback_target"
DEFAULT_PASSWORD = "geheim"
DEFAULT_parameter7z = ["-mhe=on"]
DEFAULT_exe7z_PATH_WIN = "C:\\pfadname\\7z.exe"
DEFAULT_exe7z_PATH_LINUX = "/usr/bin/7z"
DEFAULT_LOG_DIRECTORY = os.path.join(os.getcwd(), "wuergback_logs")
DEFAULT_ARCHIVE_FORMAT = "7z"

# Log-Verzeichnis erstellen, falls es nicht existiert
if not os.path.exists(DEFAULT_LOG_DIRECTORY):
    os.makedirs(DEFAULT_LOG_DIRECTORY)

# Logging konfigurieren
logging.basicConfig(
    filename=os.path.join(DEFAULT_LOG_DIRECTORY, "wuergback.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def get_default_source_dir():
    """Ermittelt das temporäre Verzeichnis des Benutzers und erstellt ein Unterverzeichnis 'wuergback'."""
    temp_dir = tempfile.gettempdir()
    default_source_dir = os.path.join(temp_dir, "wuergback")
    if not os.path.exists(default_source_dir):
        os.makedirs(default_source_dir)
    return default_source_dir

def load_config(param=None):
    """Lädt die Konfiguration aus der JSON-Datei oder erstellt eine Standardkonfiguration."""
    if param is None:
        param = CONFIG_FILE
    if not os.path.exists(param):
        default_config = {
            "source_directories": [get_default_source_dir()],
            "local_buffer_source_directory": DEFAULT_LOCAL_BUFFER_DIR,
            "backup_directory_win": DEFAULT_BACKUP_DIR_WIN,
            "backup_directory_linux": DEFAULT_BACKUP_DIR_LINUX,
            "password": DEFAULT_PASSWORD,
            "parameter7z": DEFAULT_parameter7z,
            "exe7z_path": DEFAULT_exe7z_PATH_WIN if platform.system() == "Windows" else DEFAULT_exe7z_PATH_LINUX,
            "log_directory": DEFAULT_LOG_DIRECTORY,
            "archive_format": DEFAULT_ARCHIVE_FORMAT
        }
        with open(param, "w") as file:
            json.dump(default_config, file, indent=4)
        create_default_structure(param["source_directories"][0])
        logging.info("Standardkonfiguration erstellt. Bitte überprüfen Sie die Datei %s.", param)
    with open(param, "r") as file:
        return json.load(file)

def create_default_structure(source_dir):
    """Erstellt die Standardstruktur im Quellverzeichnis."""
    if not os.path.exists(source_dir):
        os.makedirs(source_dir)
    readme_path = os.path.join(source_dir, "wuergback.readme")
    with open(readme_path, "w") as file:
        file.write(README_CONTENT)

def konfiguration_laden(welche):
        c = load_config(welche)
        # Load and check 
        local_buffer_dir = c.get("local_buffer_source_directory", DEFAULT_LOCAL_BUFFER_DIR)
        if platform.system() == "Windows": 
            backup_dir = c.get("backup_directory_win", DEFAULT_BACKUP_DIR_WIN) 
        else:
            backup_dir = c.get("backup_directory_linux", DEFAULT_BACKUP_DIR_LINUX)
        
        def schluessel(s):
            retVal= c.get(s)
            if not retVal:
                raise KeyError(f"The key exe7z [{s}] was not found in the loaded JSON data [{welche}]") 
            return retVal
        
        exe7z=schluessel("exe7z_path")
        password = c.get("password")
        source_directories = c.get("source_directories")
        parameter7z = c.get("parameter7z")
        return create_backup, source_directories, local_buffer_dir, backup_dir, password, parameter7z, exe7z

def get_exe7z(config):
    """Gibt den Pfad zur 7-Zip-Executable zurück."""
    exe7z_path = config.get("exe7z_path", DEFAULT_exe7z_PATH_WIN if platform.system() == "Windows" else DEFAULT_exe7z_PATH_LINUX)
    if not os.path.exists(exe7z_path):
        raise FileNotFoundError(f"7-Zip-Executable nicht gefunden: {exe7z_path}")
    return exe7z_path


def calculate_hash(file_path):
    """Berechnet den SHA256-Hash einer Datei."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def create_backup(source_dir, local_buffer_dir, backup_dir, password, parameter7z, exe7z):
    """Erstellt ein Backup eines Verzeichnisses."""
    try:
        # Überprüfen, ob das Zielverzeichnis bereits existiert
        if not os.path.exists(local_buffer_dir):
            os.makedirs(local_buffer_dir)
            logging.info("Angelegt: %s.", local_buffer_dir)
        # Zeitstempel generieren
        timestamp = datetime.now().strftime("%Y.%m.%d_%H-%M-%S")
        archive_name = os.path.join(local_buffer_dir, f"{os.path.basename(source_dir)}_{timestamp}.7z")
        
        if os.path.exists(archive_name):
            raise FileExistsError(f"Panik: da existiert schon was: {archive_name}")
        
        # Backup erstellen
        command = [exe7z, "a", "-p" + password, *parameter7z, archive_name, source_dir]
        subprocess.run(command, check=True)

        # Backup in das Zielverzeichnis kopieren
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        backup_archive_name = os.path.join(backup_dir, os.path.basename(archive_name))
        shutil.copy2(archive_name, backup_archive_name)

        # Hash-Berechnung und Vergleich
        local_hash = calculate_hash(archive_name)
        backup_hash = calculate_hash(backup_archive_name)

        # Constants for log and return messages
        BACKUP_MSG = f"Backup von {backup_archive_name} aus {source_dir}"
        BACKUP_SUCCESS = f"{BACKUP_MSG} erfolgreich. Hashes stimmen überein."
        BACKUP_HASH_MISMATCH = f"{BACKUP_MSG} erfolgreich, aber Hashes stimmen nicht überein!"
        BACKUP_ERROR = f"Fehler beim {BACKUP_MSG}: {{e}}"

        if local_hash == backup_hash:
            logging.info(BACKUP_SUCCESS)
            return BACKUP_SUCCESS
        else:
            logging.warning(BACKUP_HASH_MISMATCH)
            return BACKUP_HASH_MISMATCH
    except Exception as e:
        logging.error(BACKUP_ERROR.format(e=e))
        return BACKUP_ERROR.format(e=e)

def main(konfigurationsparameter):
    """Hauptfunktion des Skripts."""
    if not konfigurationsparameter:
        logging.error("Keine Konfigurationsparameter übergeben.")
        return
    try:
        execute_selbsttest()
        logging.info(f"Starte Verarbeitung der Backup-Konfigurationen: {konfigurationsparameter}") 
        for k in konfigurationsparameter: 
            result = konfiguration_laden(k)
            if result:
                create_backup_func, source_dirs, local_buffer_dir, backup_dir, password, parameter7z, exe7z = result
                backups_parallel_erstellen(create_backup_func, source_dirs, local_buffer_dir, backup_dir, password, parameter7z, exe7z)    
            else:
                raise Exception(f"Konnte nicht geladen werden: {k}") 
    except Exception as e:
        raise RuntimeError("Schwerwiegender Fehler in main(): %s", e)

def backups_parallel_erstellen(create_backup_func, source_dirs, local_buffer_dir, backup_dir, password, parameter7z, exe7z):
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(create_backup_func, source_dir, local_buffer_dir, backup_dir, password, parameter7z, exe7z) for source_dir in source_dirs]
        for future in as_completed(futures):
            result = future.result()
            logging.info(result)

def execute_selbsttest():
    try:
        test_root, source_dir, target_dir = selftest()
    except Exception as e:
        logging.error("Schwerwiegender Fehler: %s", e)

def selftest():
    """Führt einen Selbsttest durch, indem ein Testverzeichnis erstellt wird."""
    temp_dir = tempfile.gettempdir()
    test_root = os.path.join(temp_dir, "wuergback_test")
    source_dir = os.path.join(test_root, "wuergback_source")
    target_dir = os.path.join(test_root, "wuergback_target")

    # Teststruktur erstellen
    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(target_dir, exist_ok=True)

    # Testdateien erstellen
    for i in range(1, 4):
        subdir = os.path.join(source_dir, f"wtestdir_{i}")
        os.makedirs(subdir, exist_ok=True)
        test_file = os.path.join(subdir, "test.txt")
        with open(test_file, "w") as file:
            file.write("hello from wuergback")

    logging.info("Testverzeichnis erstellt unter: %s", test_root)
    return test_root, source_dir, target_dir

if __name__ == "__main__":
    konfigurationen=['wuergback']
    #konfigurationen=['RN049932_to_H']
    main(konfigurationen)
