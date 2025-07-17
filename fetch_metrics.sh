#!/bin/bash

REMOTE_USER="ubuntu"
REMOTE_HOSTS=("185.216.21.120" "185.216.21.212" "62.169.159.201" "185.216.22.230" "185.216.22.135")
CONTAINER_NAME="stt-server"
CONTAINER_LOGS_DIR="/app/logs"
REMOTE_TMP_DIR="/home/ubuntu/temp_logs"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_SAVE_DIR="${SCRIPT_DIR}/logs"
SSH_KEY="$HOME/.ssh/id_ed25519"

if [ -z "$SSH_AUTH_SOCK" ]; then
  echo "Запускаем SSH-агент..."
  eval "$(ssh-agent -s)"
fi

ssh-add -l | grep -q "$(ssh-keygen -lf $SSH_KEY | awk '{print $2}')" &>/dev/null
if [ $? -ne 0 ]; then
  echo "Добавляем ключ в SSH-агент (введите пароль один раз)..."
  ssh-add $SSH_KEY
fi

copy_yearly_logs() {
  local host=$1
  local current_year=$(date +%Y)
  
  echo "Создаем временную директорию на сервере ${host}..."
  ssh ${REMOTE_USER}@${host} "rm -rf ${REMOTE_TMP_DIR} && mkdir -p ${REMOTE_TMP_DIR}"

  echo "Проверяем наличие директории ${current_year} в контейнере..."
  if ! ssh ${REMOTE_USER}@${host} "docker exec ${CONTAINER_NAME} test -d ${CONTAINER_LOGS_DIR}/${current_year}"; then
    echo "Директория ${current_year} не найдена на сервере ${host}"
    return 0
  fi

  echo "Копируем логи года ${current_year} из Docker-контейнера на сервер ${host}..."
  ssh ${REMOTE_USER}@${host} "docker exec ${CONTAINER_NAME} bash -c 'cd ${CONTAINER_LOGS_DIR}/${current_year} && tar -czf - *.log' | tar -xzf - -C ${REMOTE_TMP_DIR}"

  # Проверяем, есть ли файлы для копирования
  if ssh ${REMOTE_USER}@${host} "[ -z \"\$(ls -A ${REMOTE_TMP_DIR})\" ]"; then
    echo "Не найдено логов за ${current_year} год на сервере ${host}"
    return 0
  fi

  # Выводим список найденных файлов
  echo "Найдены следующие файлы за ${current_year} год:"
  ssh ${REMOTE_USER}@${host} "ls -l ${REMOTE_TMP_DIR}"

  # Создаем локальную директорию для этого хоста и года
  local host_dir="${LOCAL_SAVE_DIR}/${host}/${current_year}"
  mkdir -p "${host_dir}"

  echo "Копируем логи с сервера ${host} локально..."
  scp -r ${REMOTE_USER}@${host}:${REMOTE_TMP_DIR}/* "${host_dir}/"

  if [ $? -ne 0 ]; then
    echo "Ошибка при копировании логов с сервера ${host}."
    return 1
  fi

  # Очищаем временную директорию на удаленном сервере
  ssh ${REMOTE_USER}@${host} "rm -rf ${REMOTE_TMP_DIR}"

  echo "Логи за ${current_year} год с сервера ${host} успешно скопированы в ${host_dir}"
  return 0
}

for HOST in "${REMOTE_HOSTS[@]}"; do
  echo "Обрабатываем сервер ${HOST}..."
  copy_yearly_logs "${HOST}"
done

echo "Операция завершена."
