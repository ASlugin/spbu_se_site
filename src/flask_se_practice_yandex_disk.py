"""
   Copyright 2023 Alexander Slugin

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""
# -*- coding: utf-8 -*-
# https://yandex.ru/dev/id/doc/ru/codes/code-url

import base64
import json
import os
import tempfile

import requests
import yadisk

from flask import redirect, url_for, request, flash, session, get_flashed_messages
from flask_se_auth import login_required
from flask_se_practice_table import edit_table
from flask_se_practice_config import (
    YANDEX_CLIENT_ID,
    YANDEX_SECRET,
    YANDEX_AUTHORIZE_URL_TEMPLATE,
    YANDEX_GET_TOKEN_URL,
)


def handle_yandex_table(
    table_name, sheet_name, area_id, worktype_id, column_names_list
):
    session["table_path"] = table_name
    session["sheet_name"] = sheet_name
    session["area_id"] = area_id
    session["worktype_id"] = worktype_id
    session["column_names_list"] = column_names_list
    return get_code()


def get_code():
    redirect_uri = (
        request.environ.get("wsgi.url_scheme")
        + "://"
        + request.environ.get("HTTP_HOST")
        + url_for(yandex_code.__name__)
    )
    url = YANDEX_AUTHORIZE_URL_TEMPLATE.substitute(
        yandex_client_id=YANDEX_CLIENT_ID, redirect_uri=redirect_uri
    )
    return redirect(url)


def get_token(code):
    credentials_string = base64.b64encode(
        (YANDEX_CLIENT_ID + ":" + YANDEX_SECRET).encode("ascii")
    ).decode("ascii")
    headers = {"Authorization": "Basic " + credentials_string}
    content = "grant_type=authorization_code&code=" + code
    response = requests.post(YANDEX_GET_TOKEN_URL, headers=headers, data=content)
    if not response.ok:
        return 0

    data = json.loads(response.content)
    return data["access_token"]


@login_required
def yandex_code():
    area_id = session.get("area_id")
    worktype_id = session.get("worktype_id")
    code = request.args.get("code", type=str)
    if code is None:
        return redirect(
            url_for("index_admin", area_id=area_id, worktype_id=worktype_id)
        )

    token = get_token(code)
    disk = yadisk.YaDisk(token=token)
    if not disk.check_token():
        flash("Неверный токен для Яндекс Диска", category="error")
        return redirect(
            url_for("index_admin", area_id=area_id, worktype_id=worktype_id)
        )

    table_path = session.get("table_path")
    table_name = table_path.split("/")[-1]
    with tempfile.TemporaryDirectory() as tmp_dir:
        full_filename = tmp_dir + "/" + table_name
        try:
            disk.download(table_path, full_filename)
        except yadisk.exceptions.PathNotFoundError:
            os.remove(full_filename)

        edit_table(
            path_to_table=full_filename,
            sheet_name=session.get("sheet_name"),
            area_id=area_id,
            worktype_id=worktype_id,
            column_names_list=session.get("column_names_list"),
        )

        try:
            disk.upload(full_filename, table_path, overwrite=True)
        except yadisk.exceptions.ParentNotFoundError:
            flash("Указанный путь не существует на диске", category="error")

    flashed_messages = get_flashed_messages(category_filter=["error"])
    if len(flashed_messages) > 0:
        for message in flashed_messages:
            flash(message, category="error")
    else:
        flash("Таблица успешно загружена на Яндекс Диск", category="success")
    return redirect(url_for("index_admin", area_id=area_id, worktype_id=worktype_id))
