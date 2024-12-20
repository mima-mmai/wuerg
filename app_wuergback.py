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

def get_default_dirs_in_temp_dir(was):
    """Ermittelt das temporäre Verzeichnis des Benutzers und erstellt ein Unterverzeichnis."""
    temp_dir = tempfile.gettempdir()
    pfad = os.path.join(temp_dir, was)
    if not os.path.exists(pfad):
        os.makedirs(pfad)
    return pfad


CONFIG_FILE = "wuergback"
DEFAULT_LOCAL_BUFFER_DIR = os.path.join(os.getcwd(), "wuergback-sicherungen")
DEFAULT_BACKUP_DIR_WIN = "H:\\wuergback_target"
DEFAULT_BACKUP_DIR_LINUX = "/home/austausch/wuergback_target"
DEFAULT_PASSWORD = "geheim"
DEFAULT_parameter7z = ["-mhe=on"]
DEFAULT_exe7z_PATH_WIN = "C:\\pfadname\\7z.exe"
DEFAULT_exe7z_PATH_LINUX = "/usr/bin/7z"
DEFAULT_LOG_DIRECTORY = os.path.join(os.getcwd(), "wuergback_logs")
DEFAULT_ARCHIVE_FORMAT = "7z"
DEFAULT_SOURCE_DIRECTORY = get_default_dirs_in_temp_dir("wuergback"),



# Log-Verzeichnis erstellen, falls es nicht existiert
if not os.path.exists(DEFAULT_LOG_DIRECTORY):
    os.makedirs(DEFAULT_LOG_DIRECTORY)

# Logging konfigurieren
logging.basicConfig(
    filename=os.path.join(DEFAULT_LOG_DIRECTORY, "wuergback.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

def load_config(param=None):
    """Lädt die Konfiguration aus der JSON-Datei oder erstellt eine Standardkonfiguration."""
    if param is None:
        param = os.path.join(os.getcwd(), CONFIG_FILE)
    if not param.endswith(".json"):
        param = f"{param}.json"
    if not os.path.exists(param):
        default_config = {
            "source_directories": DEFAULT_SOURCE_DIRECTORY,
            "local_buffer_source_directory": DEFAULT_LOCAL_BUFFER_DIR,
            "backup_directory_win": DEFAULT_BACKUP_DIR_WIN,
            "backup_directory_linux": DEFAULT_BACKUP_DIR_LINUX,
            "password": DEFAULT_PASSWORD,
            "parameter7z": DEFAULT_parameter7z,
            "exe7z_path": DEFAULT_exe7z_PATH_WIN if platform.system() == "Windows" else DEFAULT_exe7z_PATH_LINUX,
            "log_directory": DEFAULT_LOG_DIRECTORY,
            #"log_directory": get_default_dirs_in_temp_dir("wuergback_logs"),
            "archive_format": DEFAULT_ARCHIVE_FORMAT
        }
        with open(param, "w") as file:
            json.dump(default_config, file, indent=4)
        create_default_structure(default_config["source_directories"][0])
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
        #log_directory = c.get("log_directory", DEFAULT_LOCAL_BUFFER_DIR)
        #Todo: Laden und dann dorhin loggen
        # Load and falback, if not set 
        local_buffer_dir = c.get("local_buffer_source_directory", DEFAULT_LOCAL_BUFFER_DIR)
        if platform.system() == "Windows": 
            backup_dir = c.get("backup_directory_win", DEFAULT_BACKUP_DIR_WIN) 
        else:
            backup_dir = c.get("backup_directory_linux", DEFAULT_BACKUP_DIR_LINUX)

        # Load and verify        
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
    ERGEBNIS_MSG =f"Backup of {source_dir}:"
    try:
        # Überprüfen, ob das Zwischenzielverzeichnis bereits existiert
        if not os.path.exists(local_buffer_dir):
            try: 
                os.makedirs(local_buffer_dir)
                logging.info(f"ok: {local_buffer_dir} wurde angelegt")
            except Exception as x:
                raise FileNotFoundError(f"Panik: {local_buffer_dir} konnte nicht angelgt werden.")    
        else:
            logging.info(f"OK: {local_buffer_dir} bereits vorhanden.")
    
        # Zwischenzielarchiv mit Zeitstempel
        archive_name = f"{os.path.basename(source_dir)}_{datetime.now().strftime("%Y.%m.%d_%H-%M-%S")}.7z"
        # Targetarchiv ohne Zeitstempel (overwrite!)
        backup_archive_name = f"{os.path.basename(source_dir)}.7z"
        
        #Zwischenziel verifizieren
        zwischenziel = os.path.join(local_buffer_dir, f"{os.path.basename(archive_name)}")
        if os.path.exists(zwischenziel):
            logging.debug("NOK: {zwischenziel} bereits vorhanden.")
            raise FileExistsError(f"Panik: Zwischenielarchiv existiert schon: {archive_name}")
        else:
            logging.debug(f"ok: Zwischenzielarchiv wird im target neu angelegt: {archive_name} werden...")

        #target erzeugen und verifizieren
        backuptarget=os.path.join(backup_dir, f"{os.path.basename(backup_archive_name)}")
        backuptarget_erzeugen_und_verifizieren(backuptarget, f"Zielarchiv({backup_archive_name})")

        #backuptool verifizieren
        if not os.path.exists(exe7z):
            raise FileExistsError(f"Panik: da ist kein backuptool {exe7z}. Lokal, geheim, manuell setzen!")
        else:
            logging.debug(f"OK: backuptool {exe7z} gefunden...")
        
        # Backup erstellen
        command = [exe7z, "a", "-p" + f"{password},user.", *parameter7z, zwischenziel, source_dir]
        logging.debug(f"OK: Starte Backup: {command}".replace(',user.',""))
        logging.info(f"OK: Erzeuge Archiv... {os.path.basename(exe7z)}: {source_dir} --> {archive_name}")
        subprocess.run(command, check=True)

        Zwischenarchiv_nach_backuptarget_kopieren (zwischenziel, backuptarget)
   
        ERGEBNIS_MSG =f"ERGEBNIS: [{source_dir}]: {Hash_Berechnung_und_Vergleich(zwischenziel, backuptarget)}"
        return True, ERGEBNIS_MSG 
    except Exception as e:
        problem=f"Fehler beim {ERGEBNIS_MSG}: {e}"
        logging.error(problem)
        return False, problem

def backuptarget_erzeugen_und_verifizieren(pfad, name):
    if os.path.exists(pfad):
        logging.info(f"ok: {name} existiert schon und wird überschrieben: {pfad} werden...")
    else:
        logging.debug(f"ok: {name} wird im target neu angelegt: {pfad} werden...")
        if not os.path.exists(pfad):
            try: 
                os.makedirs(pfad)
                logging.info(f"ok: {pfad} wurde angelegt")
            except Exception as x:
                raise FileNotFoundError(f"Panik: {pfad} konnte nicht angelegt werden.")    
        else:
            logging.info(f"OK: {pfad} bereits vorhanden.")

def Zwischenarchiv_nach_backuptarget_kopieren(quelle, ziel):
    logging.info(f"OK: Target name: {os.path.basename(quelle)}-{os.path.basename(ziel)}")    
    logging.debug(f"ok: kopiere {quelle} --> {ziel}")
    shutil.copy2(quelle, ziel)
    logging.debug(f"OK: Kopieren abgeschlossen.")


def Hash_Berechnung_und_Vergleich(a_name, ba_name):
    local_hash = calculate_hash(a_name)
    backup_hash = calculate_hash(ba_name)
    if local_hash == backup_hash:
        retVal = f"OK: Hashes stimmen überein: Backup erfolgreich."
        logging.info(retVal)
    else:
        retVal = f"NOK: Hashes stimmen *nicht* überein! Backup nicht so erfolgreich"
        logging.warning(retVal)
    return retVal

def main(konfigurationsparameter):
    """Hauptfunktion des Skripts."""
    if not konfigurationsparameter:
        logging.error("Keine Konfigurationsparameter übergeben.")
        return
    try:
        execute_selbsttest()
        logging.info(f"OK: Starte Verarbeitung der Backup-Konfigurationen: {konfigurationsparameter}") 
        for k in konfigurationsparameter: 
            result = konfiguration_laden(k)
            if result:
                create_backup_func, source_dirs, local_buffer_dir, backup_dir, password, parameter7z, exe7z = result
                backups_parallel_erstellen(create_backup_func, source_dirs, local_buffer_dir, backup_dir, password, parameter7z, exe7z)    
            else:
                raise Exception(f"Konnte nicht geladen werden: [{k}]") 
    except Exception as e:
        raise RuntimeError(f"Schwerwiegender Fehler in main(): [{e}]")

def backups_parallel_erstellen(create_backup_func, source_dirs, local_buffer_dir, backup_dir, password, parameter7z, exe7z):
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(create_backup_func, source_dir, local_buffer_dir, backup_dir, password, parameter7z, exe7z) for source_dir in source_dirs]
        gesamtergebnis = None
        for future in as_completed(futures):
            result = future.result()
            if result[0] == None or result[0] == False:
                gesamtergebnis=False
            logging.info(f"OK: Backup beendet. Kein Fehler {result[1]}")
        if gesamtergebnis ==False:
            logging.info(f"{result[1]}")
            raise RuntimeError (f"NOK: Während des Backups traten Fehler auf (!), siehe Logfile: {result[1]}")
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
