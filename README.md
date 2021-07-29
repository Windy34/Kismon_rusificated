# Kismon на русском!

Данный проект является русифицированной версией <a href="https://github.com/Kismon/kismon">Kismon</a>
![kism](https://user-images.githubusercontent.com/61827585/127535525-6ac7d41d-a568-4092-a40d-c48180100fa2.png)


## Установка
В первую очередь необходимо скачать репозиторий Kismon_rusificated

## Если у вас еще не установлен Kismon:

1. Скачиваем необходимые библиотеки, а также сам Kismon
```
$ sudo apt-get install git python3 python3-gi gir1.2-gtk-3.0 \
 gir1.2-gdkpixbuf-2.0 python3-cairo python3-simplejson \
 gir1.2-osmgpsmap-1.0
$ cd ~
$ git clone https://github.com/Kismon/kismon.git kismon
```
2. Скачиваем данный репозиторий
```
$ cd ~
$ git clone https://github.com/Windy34/Kismon_rusificated.git

```
3. Заменяем содержимое папки ~/kismon/kismon файлами репозитория Kismon_rusificated.git и собираем проект

```
$ cp Kismon_rusificated/* /kismon/kismon
$ cd kismon
$ python3 setup.py build
$ sudo python3 setup.py install

```
## Если Kismon уже установлен:
Необходимо скачать данный репозиторий и заменить содержимое /kismon/kismon скачанными файлами,
не забыть заного собрать проект. 
```
$ python3 setup.py build
$ sudo python3 setup.py install

```

## Ссылки 
* Официальный сайт:  https://www.salecker.org/software/kismon.html
* Репозиторий исходного кода:  https://github.com/Kismon/kismon
