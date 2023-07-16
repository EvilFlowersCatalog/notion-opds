from datetime import datetime
from typing import Literal, List

import click
from flask import Flask, jsonify, Response, abort
from pydantic_xml import BaseXmlModel, attr, element
from redis.client import Redis

from notion_opds.ext import cache
from notion_opds.notion import Notion

app = Flask(__name__)
app.config.from_prefixed_env()
cache.init_app(app)
notion = Notion(app)


class Author(BaseXmlModel, tag='author'):
    id: str = element()


class Content(BaseXmlModel, tag='content'):
    type: str = attr()
    value: str


class Link(BaseXmlModel, tag='link'):
    rel: str = Literal['self', 'start', 'up', 'related', 'subsection', 'http://opds-spec.org/sort/popular']
    href: str = attr()
    type: str = attr()


class AcquisitionEntry(BaseXmlModel, tag='entry', nsmap={'dc': 'http://purl.org/dc/terms/'}):
    pass


class NavigationEntry(BaseXmlModel, tag='entry'):
    title: str = element()
    links: List[Link] = element(tag='link')
    updated: str = element()
    id: str = element()
    content: Content = element()


class Feed(BaseXmlModel, tag='feed', nsmap={'': 'http://www.w3.org/2005/Atom'}):
    id: str = element()
    links: List[Link] = element(tag='link')
    title: str = element()
    updated: str = element()
    author: Author = element()
    entries: List[NavigationEntry] = element(tag='entry')


@app.route('/opds/1.2/<database_id>')
def root(database_id: str):
    database = notion.get_database(database_id)

    entries = []
    for category in database.properties[app.config['ROOT_PROPERTY']].options:
        entries.append(NavigationEntry(
            title=category.name,
            id=category.id,
            links=[
                Link(
                    rel='subsection',
                    href=f'/opds/1.2/{database.id}/{category.name}',
                    type="application/atom+xml;profile=opds-catalog;kind=navigation"
                )
            ],
            updated=database.updated_at.isoformat(),
            content=Content(type='text', value=category.name)
        ))

    feed = Feed(
        id=str(database.id),
        links=[
            Link(
                rel='self',
                href=f"/opds/1.2/{database.id}",
                type="application/atom+xml;profile=opds-catalog;kind=navigation"
            ),
            Link(
                rel='start',
                href=f"{app.config['BASE_URL']}/opds/1.2/{database.id}",
                type="application/atom+xml;profile=opds-catalog;kind=navigation"
            )
        ],
        title=database.title,
        updated=database.updated_at.isoformat(),
        author=Author(id=str(database.author_id)),
        entries=entries
    )

    xml = feed.to_xml(
        pretty_print=True,
        encoding='UTF-8',
        standalone=True
    )

    return Response(xml, mimetype='application/atom+xml;profile=opds-catalog;kind=navigation')


@app.route('/opds/1.2/<database_id>/<feed_name>')
def acquisition_feed(database_id, feed_name):
    database = notion.get_database(database_id)
    category = next(x for x in database.properties[app.config['ROOT_PROPERTY']].options if x.name == feed_name)

    if not category:
        return abort(404)

    entries = []
    items, next_cursor = notion.query_database({
        'and': [
            {
                'property': category.name,
                'select': {
                    'equals': feed_name
                }
            }
        ]
    })
    for entry in items:
        pass

    links = [
        Link(
            rel='self',
            href=f"/opds/1.2/{database_id}/{feed_name}",
            type="application/atom+xml;profile=opds-catalog;kind=acquisition"
        ),
        Link(
            rel='start',
            href=f"/opds/1.2/{database_id}",
            type="application/atom+xml;profile=opds-catalog;kind=navigation"
        ),
        Link(
            rel='first',
            href=f"/opds/1.2/{database_id}",
            type="application/atom+xml;profile=opds-catalog;kind=navigation"
        ),
        Link(
            rel='up',
            href=f"/opds/1.2/{database_id}",
            type="application/atom+xml;profile=opds-catalog;kind=navigation"
        )
    ]

    feed = Feed(
        id=category.id,
        links=links,
        title=feed_name,
        updated=database.updated_at.isoformat(),
        author=Author(id=str(database.author_id)),
        entries=[]
    )

    xml = feed.to_xml(
        pretty_print=True,
        encoding='UTF-8',
        standalone=True
    )

    return Response(xml, mimetype='application/atom+xml;profile=opds-catalog;kind=acquisition')


@app.route('/opds/1.2/<database_id>/<feed_id>/<facet>/<value>')
def facet_feed(database_id, feed_id, facet, value):
    database = notion.get_database(database_id)

    feed = Feed(
        id=str(feed_id),
        links=[
            Link(
                rel='self',
                href=f"/opds/1.2/{database_id}/",
                type="application/atom+xml;profile=opds-catalog;kind=navigation"
            ),
            Link(
                rel='start',
                href=f"{app.config['BASE_URL']}/opds/1.2/{database_id}",
                type="application/atom+xml;profile=opds-catalog;kind=navigation"
            )
        ],
        title=database.title,
        updated=database.updated_at.isoformat(),
        author=Author(id=str(database.author_id)),
        entries=[]
    )


@app.route('/v1/status')
def status():
    return jsonify({
        'timestamp': datetime.now().isoformat()
    })
