import sqlite3
import os, shutil
import itertools
import hashlib

import requests
import re
import io, zipfile, json
import giga

from errors import *

__path_to_host__ = 'http://localhost:8000/'


# Команда для запуска сервера:
# uvicorn remoting:app --host 0.0.0.0 --port 8000


# class Note:
#     def __init__(self, id_note: int, name: str, text: str):
#         self.id_note = id_note
#         self.name = name
#         self.text = text

def synchro() -> bool:
    # to_close = []
    db = sqlite3.connect("mainbase.db")
    # with sqlite3.connect() as db:
    print("mainbase.db открыта synchro()")
    cursor = db.cursor()
    cursor.execute("SELECT id_user, latest FROM user;")
    id_user, f_user = cursor.fetchone()
    if f_user:
        db.close()
        return True

    # db = sqlite3.connect("mainbase.db")
    print("mainbase.py открыта synchro()")
    try:
        response = requests.get(__path_to_host__ + "check/")
        print(response.status_code, response.json())
    except requests.RequestException as e:
        # raise NotConnect(f"Ошибка сети: {e}")
        print(NotConnect(f"Ошибка сети: {e}"))
        db.close()
        return False

    cursor.execute("SELECT id_section, name, color, id_root FROM sections WHERE latest = FALSE;")
    sections = cursor.fetchall()

    folders = []
    for row in sections:
        cursor.execute("SELECT id_folder, name, id_section FROM folders WHERE id_section = ? AND latest = FALSE",
                       (row[0],))
        folders += cursor.fetchall()

    file_notes = []
    # files.append(
    #         ("photos", (path, open(path, "rb"), "application/octet-stream"))
    #     )
    notes = []
    for row in folders:
        cursor.execute(
            "SELECT id_note, name, cnt_photos, id_folder FROM notes WHERE id_folder = ? AND latest = FALSE;",
            (row[0],))
        cur_folder = cursor.fetchall()
        for i in range(len(cur_folder)):
            file_notes.append(("file_notes",
                               (str(cur_folder[i][0]), open(f"notes/{cur_folder[i][0]}.txt", "rb"),
                                "application/octet-stream")))
            notes.append(cur_folder[i])

    file_photos = []
    photos = []
    for row in notes:
        cursor.execute("SELECT id_photo, name, size, id_note FROM photos WHERE id_note = ?",
                       (row[0],))
        cur_note = cursor.fetchall()
        for i in range(len(cur_note)):
            file_photos.append(("photos",
                                (f"{cur_note[i][-1]}/{cur_note[i][1]}",
                                 open(f"imgs/{cur_note[i][-1]}/{cur_note[i][1]}", "rb"),
                                 "application/octet-stream")))
            photos.append(cur_note[i])

    cursor.execute("SELECT * FROM deleted;")
    deleted = cursor.fetchall()

    cursor.execute("SELECT seq FROM sqlite_sequence;")
    seqs = [x[0] for x in cursor.fetchall()]
    print(seqs)

    payload = {"id_user": id_user, "sections": sections, "folders": folders,
               "notes": notes, "photos": photos, "deleted": deleted, "seqs": seqs}

    # with open("out.json", "w", encoding="utf-8") as f:
    #     json.dump(payload, f, ensure_ascii=False, indent=4)

    try:
        response = requests.post(__path_to_host__ + "all/",
                                 data={"json_str": json.dumps(payload)},
                                 files=file_photos + file_notes)
        print(response.status_code, response.json())
    except requests.RequestException as e:
        # raise NotConnect(f"Ошибка сети: {e}")
        print(NotConnect(f"Ошибка сети: {e}"))
        db.close()
        return False

        # for f in to_close:
        #     f.close()

    print("mainbase.py открыта synchro()")
    for row in notes:
        cursor.execute("UPDATE notes SET latest = TRUE WHERE id_note = ?", (row[0],))
    for row in folders:
        cursor.execute("UPDATE folders SET latest = TRUE WHERE id_folder = ?", (row[0],))
    for row in sections:
        cursor.execute("UPDATE sections SET latest = TRUE WHERE id_section = ?", (row[0],))
    cursor.execute("UPDATE user SET latest = TRUE;")
    cursor.execute("DELETE FROM deleted;")
    print("mainbase.py закрыта synchro()")
    db.commit()
    db.close()
    return True


def new_photo(id_note: int, path: str, size: int, name: str = "") -> str:
    if name == "":
        name = path.split('/')[-1]
    db = sqlite3.connect("mainbase.db")
    print("mainbase.py открыта new_photo()")
    cursor = db.cursor()
    cursor.execute("SELECT name FROM photos WHERE id_note = ?;", (id_note,))
    # result = cursor.fetchall()
    if name in itertools.chain(cursor.fetchall()):
        db.close()
        raise OccupiedName("photo", name)
    cursor.execute("INSERT INTO photos (name, size, id_note) VALUES (?, ?, ?)",
                   (name, size, id_note))
    # cursor.execute("SELECT seq FROM sqlite_sequence WHERE name = photos;")
    if not os.path.exists(f"imgs/{id_note}"):
        os.mkdir(f"imgs/{id_note}")
    shutil.copyfile(path, f"imgs/{id_note}/{name}")
    db.commit()
    db.close()
    return f"imgs/{id_note}/{name}"


def giga_photo(id_note: int, name_photo: str, query: str) -> str:
    db = sqlite3.connect("mainbase.db")
    print("mainbase.py открыта giga_pgoto()")
    cursor = db.cursor()
    cursor.execute("SELECT name FROM photos WHERE id_note = ?;", (id_note,))
    # result = cursor.fetchall()
    if f"{name_photo}.png" in itertools.chain(cursor.fetchall()):
        db.close()
        raise OccupiedName("photo", name_photo)
    try:
        giga.gen_photo(query, f"imgs/{id_note}/{name_photo}.png")
    except ConnectError as e:
        db.close()
        raise NotConnect(str(e))
    cursor.execute("INSERT INTO photos (name, size, id_note) VALUES (?, ?, ?)",
                   (f"{name_photo}.png", 700, id_note))
    # cursor.execute("SELECT seq FROM sqlite_sequence WHERE name = photos;")
    if not os.path.exists(f"imgs/{id_note}"):
        os.mkdir(f"imgs/{id_note}")
    db.commit()
    db.close()
    return f"imgs/{id_note}/{name_photo}.png"


def resize_photo(id_photo: int, size: int) -> None:
    db = sqlite3.connect("mainbase.db")
    print("mainbase.py открыта rezise_photo()")
    cursor = db.cursor()
    cursor.execute("UPDATE photos SET size = ? WHERE id_photo = ?;", (size, id_photo))
    cursor.execute("SELECT id_note FROM photos WHERE id_photo = ?;", (id_photo,))
    id_note = cursor.fetchone()[0]
    cursor.execute("SELECT id_folder FROM notes WHERE id_note = ?;", (id_note,))
    id_folder = cursor.fetchone()[0]
    cursor.execute("SELECT id_section FROM folders WHERE id_folder = ?;", (id_folder,))
    id_section = cursor.fetchone()[0]
    cursor.execute("UPDATE notes SET latest = FALSE WHERE id_note = ?", (id_note,))
    cursor.execute("UPDATE folders SET latest = FALSE WHERE id_folder = ?", (id_folder,))
    cursor.execute("UPDATE sections SET latest = FALSE WHERE id_section = ?", (id_section,))
    cursor.execute("UPDATE user SET latest = FALSE;")
    db.commit()
    db.close()


def get_photos(id_note: int) -> list[tuple[int, int]]:
    db = sqlite3.connect("mainbase.db")
    print("mainbase.py открыта get_photos()")
    cursor = db.cursor()
    cursor.execute("SELECT id_photo, size FROM photos WHERE id_note = ?", (id_note,))
    answer = cursor.fetchall()
    db.close()
    return answer


def list_notes(id_folder: int) -> list[tuple[int, str]]:
    """Получение списка заметок из папки"""
    db = sqlite3.connect("mainbase.db")
    print("mainbase.py открыта list_notes()")
    cursor = db.cursor()
    cursor.execute("SELECT id_note, name FROM notes WHERE id_folder = ?;", (id_folder,))
    answer = cursor.fetchall()
    db.close()
    return [] if answer is None else answer


def folder_is_empty(id_folder: int) -> bool:
    """Проверка папки на наличие в ней заметок"""
    db = sqlite3.connect("mainbase.db")
    print("mainbase.py открыта folder_is_empty()")
    cursor = db.cursor()
    cursor.execute("SELECT EXISTS (SELECT id_note FROM notes WHERE id_folder = ?);", (id_folder,))
    answer = cursor.fetchone()[0]
    db.close()
    return not answer


def text_note(id_note: int) -> str:
    """Получение текста заметки по её id"""
    with open(f"notes/{id_note}.txt", 'r', encoding="UTF-8") as note:
        return note.read()


def delete_note(id_note: int, flag: bool = True, db=None) -> None:
    """Удаление заметки по id"""
    if os.path.exists(f"notes/{id_note}.txt"):
        os.remove(f"notes/{id_note}.txt")
    if flag:
        db = sqlite3.connect("mainbase.db")
    print("mainbase.py открыта delete_note()")
    cursor = db.cursor()
    cursor.execute("DELETE FROM notes WHERE id_note = ?;", (id_note,))
    cursor.execute("INSERT INTO deleted (name, id) VALUES (\"notes\", ?);", (id_note,))
    cursor.execute("SELECT id_photo, name FROM photos WHERE id_note = ?;", (id_note,))
    photos = cursor.fetchall()
    shutil.rmtree(f"imgs/{id_note}")
    for img in photos:
        # os.remove(f"imgs/{id_note}/{img[1]}")
        cursor.execute("DELETE FROM photos WHERE id_photo = ?;", (img[0],))
        cursor.execute("INSERT INTO deleted (name, id) VALUES (\"photos\", ?);", (img[0],))
    cursor.execute("UPDATE user SET latest = FALSE;")
    if flag:
        db.commit()
        db.close()


def delete_folder(id_folder: int, flag: bool = True, db=None):
    """Удаление папки со всеми заметками внутри"""
    if flag:
        db = sqlite3.connect("mainbase.db")
    print("mainbase.py открыта delete_folder()")
    cursor = db.cursor()
    cursor.execute("SELECT id_note FROM notes WHERE id_folder = ?", (id_folder,))
    for id_note in [x[0] for x in cursor.fetchall()]:
        delete_note(id_note, False, db)
    cursor.execute("DELETE FROM folders WHERE id_folder = ?;", (id_folder,))
    cursor.execute("INSERT INTO deleted (name, id) VALUES (\"folders\", ?);", (id_folder,))
    cursor.execute("UPDATE user SET latest = FALSE;")
    if flag:
        db.commit()
        db.close()


def save_note(id_note: int, text: str, name: str = "") -> None:
    """Сохранение заметки"""
    id_folder = None
    # id_user = __get_id_user__()
    db = sqlite3.connect("mainbase.db")
    print("mainbase.py открыта save_note()")
    cursor = db.cursor()
    cursor.execute("SELECT id_folder FROM notes WHERE id_note = ?;", (id_note,))
    id_folder = cursor.fetchone()[0]
    if name != "":
        cursor.execute("SELECT EXISTS(SELECT NULL FROM notes WHERE id_folder = ? AND name = ?);",
                       (id_folder, name))
        if cursor.fetchone()[0]:
            db.close()
            raise OccupiedName("note", name)
        cursor.execute("UPDATE notes SET name = ? WHERE id_note = ?", (name, id_note))
        # if not os.path.exists(f"imgs/{id_note}"):
        #     os.mkdir(f"imgs/{id_note}")

    # conn = synchro()
    # if os.path.exists(f"notes/{id_note}.txt"):
    if name == '':
        with open(f"notes/{id_note}.txt", 'r', encoding="UTF-8") as note:
            if text == note.read():
                db.close()
                raise NotChange
    with open(f"notes/{id_note}.txt", 'w', encoding="UTF-8") as note:
        note.write(text)

    # photos = []
    imgs_now = [x[-1] for x in re.findall(r"!\[(.*?)\]\(imgs/(.*?)/(.*?)\)", text)]
    # db = sqlite3.connect("mainbase.db")
    print("mainbase.py открыта save_note() (опять)")
    cursor = db.cursor()
    cursor.execute("SELECT * FROM photos WHERE id_note = ?;", (id_note,))
    imgs_db = cursor.fetchall()
    if len(imgs_db) > 0:
        for photo in imgs_db:
            if photo[1] not in imgs_now:
                os.remove(f"imgs/{id_note}/{photo[1]}")
                cursor.execute("DELETE FROM photos WHERE id_photo = ?", (photo[0],))
                cursor.execute("INSERT INTO deleted (name, id) VALUES (\"photos\", ?)", (photo[0],))
            # else:
            #     cursor.execute("SELECT id_photo, name, size FROM photos WHERE id_note = ?", (id_note,))
            # photos.append(cursor.fetchone())

    cursor.execute("UPDATE notes SET latest = FALSE WHERE id_note = ?", (id_note,))
    cursor.execute("SELECT id_section FROM folders WHERE id_folder = ?", (id_folder,))
    id_section = cursor.fetchone()[0]
    cursor.execute("UPDATE sections SET latest = FALSE WHERE id_section = ?;",
                   (id_section,))
    cursor.execute("UPDATE folders SET latest = FALSE WHERE id_folder = ?;", (id_folder,))
    cursor.execute("UPDATE user SET latest = FALSE;")

    # if not conn: return False
    # payload = {"id_local": id_note, "name": name, "id_user": id_user, "id_local_folder": id_folder, "photos": photos}
    # note = ("note", (str(id_note), open(f"notes/{id_note}.txt", "rb"), "application/octet-stream"))
    #
    # file_photos = []
    # for img in imgs_now:
    #     file_photos.append(
    #         ("photos", (f"{id_note}/{img}", open(f"imgs/{id_note}/{img}", "rb"), "application/octet-stream")))

    # try:
    #     response = requests.post(__path_to_host__ + "notes/",
    #                              data={"json_str": json.dumps(payload)},
    #                              files=file_photos + [note])
    #     print(response.status_code, response.json())
    # except requests.RequestException as e:
    #     cursor.execute("UPDATE notes SET latest = FALSE WHERE id_note = ?", (id_note,))
    #     cursor.execute("SELECT id_section FROM folders WHERE id_folder = ?", (id_folder,))
    #     id_section = cursor.fetchone()[0]
    #     cursor.execute("UPDATE sections SET latest = FALSE WHERE id_section = ?;",
    #                    (id_section,))
    #     cursor.execute("UPDATE folders SET latest = FALSE WHERE id_folder = ?;", (id_folder,))
    #     cursor.execute("UPDATE user SET latest = FALSE;")
    #     # raise NotConnect(f"Ошибка сети: {e}")
    #     print(NotConnect(f"Ошибка сети: {e}"))
    #     return False
    # return True
    db.commit()
    db.close()


class Section:
    """:param id_section
    :param name
    :param color
    :param id_user
    :param id_root"""

    def __init__(self, id_section: int, name: str, color: str, id_root: int, id_user: int):
        self.id_section = id_section
        self.name = name
        self.color = color
        self.id_user = id_user
        self.id_root = id_root

    def __repr__(self):
        return f"{'{'}\"id_section\": {self.id_section}, \"name\": \"{self.name}\", \"color\": \"{self.color}\", \"id_user\": {self.id_user}, \"id_root\": {self.id_root}{'}'}"

    def menu(self) -> list[list[tuple[int, str]]]:
        """Получение списка заметок и папок из раздела"""
        db = sqlite3.connect("mainbase.db")
        print("mainbase.py открыта Section.menu()")
        cursor = db.cursor()
        cursor.execute("SELECT id_folder, name FROM folders WHERE id_section = ? AND name IS NOT NULL;",
                       (self.id_section,))
        answer = [cursor.fetchall()]
        answer += [list_notes(self.id_root)]
        db.close()
        return [] if answer is None else answer

    def create_folder(self, name: str) -> None:
        """Создание папки"""
        # conn = synchro()
        # try:
        #     synchro()
        # except (requests.RequestException, NotConnect) as e:
        #     print(NotConnect(f"Ошибка сети: {e}"))
        #     conn = False

        db = sqlite3.connect("mainbase.db")
        print("mainbase.py открыта Section.create_folder()")
        cursor = db.cursor()
        cursor.execute("SELECT EXISTS(SELECT * FROM folders WHERE id_section = ? AND name = ?);",
                       (self.id_section, name))
        if cursor.fetchone()[0]:
            db.close()
            raise OccupiedName("folder", name)
        cursor.execute("INSERT INTO folders (name, id_section) VALUES (?, ?);",
                       (name, self.id_section))
        id_folder = cursor.lastrowid

        cursor.execute("UPDATE sections SET latest = FALSE WHERE id_section = ?;",
                       (self.id_section,))
        cursor.execute("UPDATE folders SET latest = FALSE WHERE id_folder = ?;", (id_folder,))
        cursor.execute("UPDATE user SET latest = FALSE;")
        # if not conn: return False
        # try:
        #     response = requests.post(__path_to_host__ + "folders/",
        #                              json={"id_local": id_folder, "name": name, "id_user": self.id_user,
        #                                    "id_local_section": self.id_section})
        #     print(response.status_code, response.json())
        # except (requests.RequestException, NotConnect) as e:
        #     cursor.execute("UPDATE sections SET latest = FALSE WHERE id_section = ?;",
        #                    (self.id_section,))
        #     cursor.execute("UPDATE folders SET latest = FALSE WHERE id_folder = ?;", (id_folder,))
        #     cursor.execute("UPDATE user SET latest = FALSE;")
        #     # raise NotConnect(f"Ошибка сети: {e}")
        #     print(NotConnect(f"Ошибка сети: {e}"))
        #     return False
        # return True
        db.commit()
        db.close()

    def reserve_note(self, id_folder: int = 0) -> int:
        """Создание заметки"""
        if not id_folder:
            id_folder = self.id_root
        db = sqlite3.connect("mainbase.db")
        print("mainbase.py открыта Section.reserve_note()")
        cursor = db.cursor()
        cursor.execute("INSERT INTO notes (id_folder) VALUES (?);",
                       (id_folder,))
        id_note = cursor.lastrowid
        if not os.path.exists(f"imgs/{id_note}"):
            os.mkdir(f"imgs/{id_note}")
        db.commit()
        db.close()
        return id_note

    def delete(self):
        db = sqlite3.connect("mainbase.db")
        print("mainbase.py открыта Section.delete()")
        cursor = db.cursor()
        cursor.execute("SELECT id_folder FROM folders WHERE id_section = ?", (self.id_section,))
        for id_folder in [x[0] for x in cursor.fetchall()]:
            delete_folder(id_folder, False, db)
        cursor.execute("DELETE FROM sections WHERE id_section = ?;", (self.id_section,))
        cursor.execute("INSERT INTO deleted (name, id) VALUES (\"sections\", ?);", (self.id_section,))
        cursor.execute("UPDATE user SET latest = FALSE;")
        db.commit()
        db.close()


class User:
    """Класс пользователей\n
    Содержит: id пользователя, имя, почту, пароль, id корневой папки\n"""

    def __init__(self, id_user: int, username: str, email: str, latest: bool):
        self.id_user = id_user
        self.username = username
        self.email = email
        self.latest = latest

    def create_section(self, name: str, color: str) -> None:
        # conn = synchro()
        # try:
        #     synchro()
        # except (requests.RequestException, NotConnect) as e:
        #     print(NotConnect(f"Ошибка сети: {e}"))
        #     conn = False

        db = sqlite3.connect("mainbase.db")
        print("mainbase.py открыта User.create_section()")
        cursor = db.cursor()
        cursor.execute("SELECT EXISTS(SELECT name FROM sections WHERE name = ?);", (name,))
        if cursor.fetchone()[0]:
            db.close()
            raise OccupiedName("section", name)

        cursor.execute("INSERT INTO sections (name, color, id_root) VALUES (?, ?, ?)",
                       (name, color, -1))
        id_section = cursor.lastrowid

        cursor.execute("INSERT INTO folders (id_section) VALUES (?);", (id_section,))
        id_root = cursor.lastrowid
        cursor.execute("UPDATE sections SET id_root = ? WHERE id_section = ?;",
                       (id_root, id_section))

        cursor.execute("UPDATE sections SET latest = FALSE WHERE id_section = ?;", (id_section,))
        cursor.execute("UPDATE folders SET latest = FALSE WHERE id_folder = ?;", (id_root,))
        cursor.execute("UPDATE user SET latest = FALSE;")
        # if not conn: return False
        # try:
        #     response = requests.post(__path_to_host__ + "sections/",
        #                              json={"id_local": id_section, "name": name, "color": color,
        #                                    "id_user": self.id_user, "id_root": id_root})
        #     print(response.status_code, response.json())
        # except (requests.RequestException, ConnectionError) as e:
        #     cursor.execute("UPDATE sections SET latest = FALSE WHERE id_section = ?;", (id_section,))
        #     cursor.execute("UPDATE folders SET latest = FALSE WHERE id_folder = ?;", (id_root,))
        #     cursor.execute("UPDATE user SET latest = FALSE;")
        #     # raise NotConnect(f"Ошибка сети: {e}")
        #     print(NotConnect(f"Ошибка сети: {e}"))
        #     return False
        # return True
        db.commit()
        db.close()

    def list_sections(self) -> tuple[Section, ...]:
        db = sqlite3.connect("mainbase.db")
        print("mainbase.py открыта User.list_sections()")
        cursor = db.cursor()
        cursor.execute("SELECT * FROM sections;")
        answer = cursor.fetchall()
        print("mainbase.py закрыта User.list_sections()")
        db.close()
        return tuple(Section(*args[:-1], self.id_user) for args in answer)


def login_user(login: str, password: str) -> User:
    """Авторизация пользователя"""
    try:
        response = requests.get(__path_to_host__ + 'users/',
                                json={"login": login, "password": hashlib.sha256(password.encode()).hexdigest()})
        response.raise_for_status()

        answer = None
        zip_bytes = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_bytes) as zf:
            # Читаем JSON из архива
            with zf.open("data.json") as json_file:
                answer = json.load(json_file)
            print("Полученные JSON-данные:", answer)

            zf.extractall()
        # print(response.status_code, response.json())
        if os.path.exists("data.json"):
            os.remove("data.json")
    except requests.RequestException as e:
        raise NotConnect(f"Ошибка сети: {e}")
    match answer["status"]:
        case 2:
            raise UserNotExists(login)
        case 1:
            raise IncorrectPassword
        case 0:
            pass
    if os.path.exists("mainbase.db"):
        os.remove("mainbase.db")
    if not os.path.exists("imgs"):
        os.mkdir("imgs")
    if not os.path.exists("notes"):
        os.mkdir("notes")

    db = sqlite3.connect("mainbase.db")
    print("mainbase.py открыта login_user()")
    cursor = db.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS user (
                   id_user INTEGER NOT NULL,
                   username TEXT NOT NULL,
                   email TEXT NOT NULL,
                   latest BOOL DEFAULT TRUE NOT NULL);''')

    cursor.execute('''INSERT INTO user (id_user, username, email) VALUES (?, ?, ?);''',
                   (*answer["user"],))

    cursor.execute('''CREATE TABLE sections (
            id_section INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            color TEXT NOT NULL,
            id_root INTEGER UNIQUE,
            latest BOOL DEFAULT TRUE NOT NULL);''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS folders (
                    id_folder INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    id_section INTEGER NOT NULL,
                    latest BOOL DEFAULT TRUE NOT NULL,
                    FOREIGN KEY (id_section) REFERENCES sections (id_section));''')

    # cursor.execute("SELECT id_user FROM users WHERE username = ? AND email = ?;", (username, email))
    # id_user = cursor.fetchone()[0]

    # cursor.execute('''CREATE TRIGGER IF NOT EXISTS add_main_folder
    #                 AFTER INSERT ON sections
    #                 FOR EACH ROW
    #                 BEGIN
    #                     INSERT INTO folders (id_section) SELECT MAX(id_section) FROM sections;
    #                     UPDATE sections SET id_root = (
    #                     SELECT id_folder FROM folders WHERE id_section = (SELECT MAX(id_section) FROM sections) AND name IS NULL)
    #                     WHERE id_section = (SELECT MAX(id_section) FROM sections);
    #                 END;''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS notes (
                                id_note INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT,
                                cnt_photos INTEGER DEFAULT 0 NOT NULL,
                                id_folder INTEGER NOT NULL,
                                latest BOOL DEFAULT TRUE NOT NULL,
                                FOREIGN KEY (id_folder) REFERENCES folders (id_folder));''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS photos (
                        id_photo INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        size INTEGER NOT NULL,
                        id_note INTEGER NOT NULL,
                        FOREIGN KEY (id_note) REFERENCES notes (id_note));''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS deleted (
                   name TEXT NOT NULL,
                   id INTEGER NOT NULL);''')

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_section_folders ON folders (id_section);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_folder_notes ON notes (id_folder);")

    # cursor.execute('''CREATE TRIGGER IF NOT EXISTS autoincrement_notes
    # AFTER INSERT ON notes
    # FOR EACH ROW
    # BEGIN
    #     UPDATE notes SET id_note = (SELECT MAX(id_note) FROM notes) + 1
    #     WHERE id_note = NULL;
    # END;''')

    cursor.execute("INSERT INTO sections (id_section, name, color) VALUES (?, \"0\", \"0\");",
                   (answer["seqs"][0],))
    cursor.execute("DELETE FROM sections WHERE id_section = ?", (answer["seqs"][0],))

    cursor.execute("INSERT INTO folders (id_folder, id_section) VALUES (?, 0);",
                   (answer["seqs"][1],))
    cursor.execute("DELETE FROM folders WHERE id_folder = ?", (answer["seqs"][1],))

    cursor.execute("INSERT INTO notes (id_note, name, id_folder) VALUES (?, \"0\", 0);",
                   (answer["seqs"][2],))
    cursor.execute("DELETE FROM notes WHERE id_note = ?", (answer["seqs"][2],))

    cursor.execute("INSERT INTO photos (id_photo, name, size, id_note) VALUES (?, \"0\", 0, 0);",
                   (answer["seqs"][3],))
    cursor.execute("DELETE FROM photos WHERE id_photo = ?", (answer["seqs"][3],))

    for row in answer["sections"]:
        cursor.execute("INSERT INTO sections (id_section, name, color, id_root) VALUES (?, ?, ?, ?);",
                       (*row,))

    for row in answer["folders"]:
        cursor.execute("INSERT INTO folders (id_folder, name, id_section) VALUES (?, ?, ?);",
                       (*row,))

    for row in answer["notes"]:
        if row[2]:
            os.mkdir("imgs/" + str(row[0]))
        cursor.execute("INSERT INTO notes (id_note, name, cnt_photos, id_folder) VALUES (?, ?, ?, ?);",
                       (*row,))

    for row in answer["photos"]:
        # with open(f"imgs/{row[3]}/{row[1]}", "wb") as img:
        #     img.write(row[4])
        cursor.execute("INSERT INTO photos (id_photo, name, size, id_note) VALUES (?, ?, ?, ?)",
                       (*row,))
    db.commit()
    db.close()
    return User(*answer["user"], True)


def register_user(username: str, email: str, password: str) -> None:
    """Регистрация нового пользователя"""
    try:
        data = {"username": username, "email": email, "password": hashlib.sha256(password.encode()).hexdigest()}
        response = requests.post(__path_to_host__ + "users/", json=data)
        print(response.status_code, response.json())
    except requests.RequestException as e:
        raise NotConnect(f"Ошибка сети: {e}")
    match response.json()["status"]:
        case 3:
            raise OccupiedName("all")
        case 2:
            raise OccupiedName("email", email)
        case 1:
            raise OccupiedName("username", username)
        case 0:
            pass


def __get_id_user__() -> int:
    db = sqlite3.connect("mainbase.db")
    print("mainbase.py открыта __get_id_user__()")
    cursor = db.cursor()
    cursor.execute("SELECT id_user FROM user;")
    answer = cursor.fetchone()[0]
    db.close()
    return answer


def is_sync() -> bool:
    db = sqlite3.connect("mainbase.db")
    # with sqlite3.connect("mainbase.db") as db:
    print("mainbase.py открыта is_sync()")
    cursor = db.cursor()
    cursor.execute("SELECT latest FROM user;")
    answer = cursor.fetchone()[0]
    db.close()
    print("mainbase.py закрыта is_sync()")
    return bool(answer)


def logout_user():
    # for i in range(8):
    #     try:
    #         if os.path.exists("mainbase.db"):
    #             os.remove("mainbase.db")
    #         print(f"Файл {"mainbase.db"} успешно удалён.")
    #         return
    #     except PermissionError:
    #         print(f"Попытка {i + 1}: файл {"mainbase.db"} занят, подождите...")
    #         time.sleep(5)
    # with sqlite3.connect("mainbase.db") as db:
    #     print("!!!mainbase.py открыта logout_user()!!!\n")
    #     cursor = db.cursor()
    #     for table in ("user", "sections", "folders", "notes", "photos", "deleted"):
    #         cursor.execute(f"DROP TABLE {table};")
    if os.path.exists("mainbase.db"):
        os.remove("mainbase.db")
    if os.path.exists("last_drawing.png"):
        os.remove("last_drawing.png")
    shutil.rmtree("imgs")
    shutil.rmtree("notes")


def cur_login() -> None | User:
    if not os.path.exists("mainbase.db"): return
    db = sqlite3.connect("mainbase.db")
    print("mainbase.py открыта cur_login()")
    cursor = db.cursor()
    cursor.execute("SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type=\"table\" AND name=\"user\");")
    if not cursor.fetchone()[0]: return
    cursor.execute("SELECT * FROM user;")
    answer = cursor.fetchone()
    db.close()
    print("mainbase.py закрыта cur_login()")
    if answer is not None: return User(*answer)
