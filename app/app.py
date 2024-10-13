
from app.common.database import DBUser, DBForum, DBForumTopic
from app.common.database.repositories import users

from flask import Flask, Request, jsonify, redirect, request
from flask_pydantic.exceptions import ValidationError
from datetime import datetime, timedelta
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager
from typing import Tuple, Optional
from werkzeug.exceptions import *

from . import common
from . import routes
from . import bbcode

import traceback
import timeago
import config
import utils
import math
import re

flask = Flask(
    __name__,
    static_url_path='',
    static_folder='static',
    template_folder='templates'
)

flask.register_blueprint(routes.router)
flask.secret_key = config.FRONTEND_SECRET_KEY
flask.config['FLASK_PYDANTIC_VALIDATION_ERROR_RAISE'] = True

login_manager = LoginManager()
login_manager.init_app(flask)

csrf = CSRFProtect()
csrf.init_app(flask)

@login_manager.user_loader
def user_loader(user_id: int) -> Optional[DBUser]:
    try:
        user = users.fetch_by_id(
            user_id,
            DBUser.groups,
            DBUser.relationships
        )

        if not user:
            return

        return user
    except Exception as e:
        flask.logger.error(f'Failed to load user: {e}', exc_info=e)
        return None

@login_manager.request_loader
def request_loader(request: Request):
    user_id = request.form.get('id')
    return user_loader(user_id)

@login_manager.unauthorized_handler
def unauthorized_user():
    if '/api' in request.base_url:
        return jsonify(
            error=403,
            details='You are not authorized to perform this action.'
        ), 403

    return redirect('/?login=True')

@flask.errorhandler(HTTPException)
def on_http_exception(error: HTTPException) -> Tuple[str, int]:
    if '/api' in request.base_url:
        return jsonify(
            error=error.code,
            details=error.description or error.name
        ), error.code

    custom_description = getattr(
        error,
        'html_description',
        error.description or error.name
    )

    if error.description.startswith('<'):
        # Okay, I know this solution is bad, but I'm
        # too lazy to find a better one right now.
        custom_description = error.description

    return utils.render_template(
        content=custom_description,
        code=error.code,
        template_name='error.html',
        css='error.css',
        title=f'{error.name} - Titanic!'
    ), error.code

@flask.errorhandler(Exception)
def on_exception(error: Exception) -> Tuple[str, int]:
    traceback.print_exc()

    if '/api' in request.base_url:
        return jsonify(
            error=500,
            details=InternalServerError.description
        ), 500

    return utils.render_template(
        content=InternalServerError.html_description,
        code=500,
        template_name='error.html',
        css='error.css',
        title=f'Internal Server Error - Titanic!'
    ), 500

@flask.errorhandler(ValidationError)
def on_validation_error(error: ValidationError) -> Tuple[str, int]:
    params = {
        param: getattr(error, param)
        for param in (
            'body_params',
            'form_params',
            'path_params',
            'query_params'
        )
    }

    return jsonify(
        error=400,
        details={
            'validation_error': {
                name: value
                for name, value in params.items()
                if value is not None
            }
        }
    ), 400

@flask.template_filter('any')
def any_filter(value: list) -> bool:
    return any(value)

@flask.template_filter('all')
def all_filter(value: list) -> bool:
    return all(value)

@flask.template_filter('timeago')
def timeago_formatting(date: datetime):
    return timeago.format(date.replace(tzinfo=None), datetime.now())

@flask.template_filter('round')
def get_rounded(num: float, ndigits: int = 0):
    return round(num, ndigits)

@flask.template_filter('playstyle')
def get_rounded(num: int):
    return common.constants.Playstyle(num)

@flask.template_filter('domain')
def get_domain(url: str) -> str:
    return re.search(r'https?://([A-Za-z_0-9.-]+).*', url) \
             .group(1)

@flask.template_filter('twitter_handle')
def get_handle(url: str) -> str:
    url_match = re.search(r'https?://(www.)?(twitter|x)\.com/(@\w+|\w+)', url)

    if url_match:
        return url_match.group(3)

    if not url.startswith('@'):
        url = f'@{url}'

    return url

@flask.template_filter('short_mods')
def get_short(mods):
    return (
        common.constants.Mods(mods).short
        if mods else 'None'
    )

@flask.template_filter('get_level')
def get_user_level(total_score: int) -> int:
    next_level = common.constants.level.NEXT_LEVEL
    total_score = min(total_score, next_level[-1])

    index = 0
    score = 0

    while score + next_level[index] < total_score:
        score += next_level[index]
        index += 1

    return round((index + 1) + (total_score - score) / next_level[index])

@flask.template_filter('get_level_score')
def get_level_score(total_score: int) -> int:
    next_level = common.constants.level.NEXT_LEVEL
    total_score = min(total_score, next_level[-1])

    index = 0
    score = 0

    while score + next_level[index] < total_score:
        score += next_level[index]
        index += 1

    return total_score - score

@flask.template_filter('strftime')
def jinja2_strftime(date: datetime, format='%m/%d/%Y, %H:%M:%S'):
    native = date.replace(tzinfo=None)
    return native.strftime(format)

@flask.template_filter('format_activity')
def format_activity(activity_text: str, activity: common.database.DBActivity) -> str:
    links = activity.activity_links.split('||')
    args = activity.activity_args.split('||')
    items = tuple(zip(links, args))

    return activity_text \
        .format(
            *(
                f'<b><a href="{link}">{text}</a></b>'
                if '/u/' in link else
                f'<a href="{link}">{text}</a>'
                for link, text in items
            )
        )

@flask.template_filter('format_chat')
def format_chat(text: str) -> str:
    # Sanitize input text
    text = text.replace("<","&lt") \
               .replace(">", "&gt;")

    # Replace chat links with html links
    pattern = r'\[([^\s\]]+)\s+(.+?)\]'
    replacement = r'<a href="\1">\2</a>'
    result = re.sub(pattern, replacement, text)

    # Remove action text
    result = result.replace('\x01ACTION', '') \
                   .replace('\x01', '')

    return result

@flask.template_filter('round_time')
def round_time(dt: datetime, round_to = 60):
    if dt == None : dt = datetime.now()
    seconds = (dt.replace(tzinfo=None) - dt.min).seconds
    rounding = (seconds+round_to/2) // round_to * round_to
    return dt + timedelta(0,rounding-seconds,-dt.microsecond)

@flask.template_filter('get_attributes')
def get_attributes(objects: list, name: str) -> list:
    return [getattr(o, name) for o in objects]

@flask.template_filter('clamp')
def clamp_value(value: int, minimum: int, maximum: int):
    return max(minimum, min(value, maximum))

@flask.template_filter('bbcode')
def render_bbcode(text: str) -> str:
    return f'<div class="bbcode">{bbcode.render_html(text)}</div>'

@flask.template_filter('bbcode_no_wrapper')
def render_bbcode_no_wrapper(text: str) -> str:
    return bbcode.render_html(text)

@flask.template_filter('bbcode_nowrap')
def render_bbcode_nowrapper(text: str) -> str:
    return bbcode.render_html(text)

@flask.template_filter('markdown_urls')
def format_markdown_urls(value: str) -> str:
    links = list(
        re.compile(r'\[([^\]]+)\]\(([^)]+)\)').findall(value)
    )

    for link in links:
        value = value.replace(
            f'[{link[0]}]({link[1]})',
            f'<a href="{link[1]}">{link[0]}</a>'
        )

    return value

@flask.template_filter('list_parent_forums')
def list_parent_forums(forum: DBForum) -> list:
    parent_forums = []

    while forum.parent_id:
        parent_forums.append(forum.parent)
        forum = forum.parent

    return parent_forums

@flask.template_filter('user_color')
def get_user_color(user: DBUser, default='#4a4a4a') -> str:
    if not user.groups:
        return default

    primary_group_id = min(get_attributes(user.groups, 'group_id'))
    primary_group = next(group for group in user.groups if group.group_id == primary_group_id).group
    return primary_group.color

@flask.template_filter('ceil')
def ceil(value: float) -> int:
    return math.ceil(value)

@flask.template_filter('required_nominations')
def get_required_nominations(beatmapset) -> int:
    return utils.required_nominations(beatmapset)

@flask.template_filter('get_status_icon')
def get_status_icon(topic: DBForumTopic) -> str:
    if topic.pinned or topic.announcement:
        if topic.locked_at:
            return "/images/icons/topics/announce_read_locked.gif"

        return "/images/icons/topics/announce_read.gif"

    if topic.locked_at:
        return "/images/icons/topics/topic_read_locked.gif"

    time = datetime.now() - topic.created_at
    views = utils.fetch_average_topic_views()

    if (topic.views > views) and (time.days < 7):
        return "/images/icons/topics/topic_read_hot.gif"

    # TODO: Read/Unread Logic
    return "/images/icons/topics/topic_read.gif"
