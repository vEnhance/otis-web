# This is a development dockerfile, that's made in 5 minutes by Amol Rama
# If it seems bad, feel free to let him know :)
FROM python:buster

ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1
RUN pip install poetry black toml

WORKDIR /app

COPY pyproject.toml .

RUN poetry install

COPY . .

RUN . ./.env

RUN poetry run python manage.py migrate
RUN poetry run python manage.py createsuperuser --no-input

CMD ./start.sh
