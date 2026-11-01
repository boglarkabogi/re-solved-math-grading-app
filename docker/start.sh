#!/bin/sh
# A webkiszolgáló indítása. Ugyanez a szkript fut a kari szerveren és a
# Renderen is; a különbség csak a RUN_WORKER_IN_WEB kapcsoló.
set -e

cd /app/web

python manage.py migrate --noinput

# A hash-elt fájlneveket ez állítja elő. Enélkül az éles lap a legutóbbi
# collectstatic állapotát szolgálná ki, és a frissen szerkesztett CSS nem
# jutna el a böngészőig.
python manage.py collectstatic --noinput

# A Render ingyenes csomagjában nincs külön háttérszolgáltatás, ezért ott a
# feldolgozó ugyanebben a konténerben indul a gunicorn mellé. Docker compose
# esetén ez marad 0, mert ott a worker a saját szolgáltatása.
if [ "${RUN_WORKER_IN_WEB:-0}" = "1" ]; then
    echo "A feldolgozó a webkiszolgáló mellett indul (RUN_WORKER_IN_WEB=1)."

    # Ha a feldolgozó bármiért leáll, induljon újra: a sorban álló diákok
    # különben örökre várnának.
    (
        while true; do
            python manage.py run_worker || echo "A feldolgozó leállt, 5 másodperc múlva újraindul."
            sleep 5
        done
    ) &
fi

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-120}"
