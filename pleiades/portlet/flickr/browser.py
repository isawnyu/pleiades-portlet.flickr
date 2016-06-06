import logging
import requests
import simplejson
from random import choice
from time import time

from Acquisition import aq_inner, aq_parent
from plone.memoize import ram

from zope.publisher.browser import BrowserView

from Products.PleiadesEntity.content.interfaces import ILocation, IName, IPlace

log = logging.getLogger("pleiades.portlet.flickr")

FLICKR_API_ENDPOINT = "https://api.flickr.com/services/rest/"
FLICKR_API_KEY = "b5899a9f7069f933b46b32b949ab4afd"
FLICKR_TAGS_BASE = "https://www.flickr.com/photos/tags/"
PLEIADES_PLACES_ID = "1876758@N22"
IMG_TMPL = "https://farm%(farm)s.staticflickr.com/%(server)s/%(id)s_%(secret)s_m.jpg"
PAGE_TMPL = "https://flickr.com/photos/%(owner)s/%(id)s/in/pool-1876758@N22"


def _flickr_cache_key(method, self, pid):
    # Two hour RAM cache on API requests
    cache_time = time() // (2 * 60 * 60)
    return '{}/{}/{}'.format(method.__name__, pid, cache_time)


class FlickrResponseError(ValueError):
    """An error in a Flickr API Response"""


class RelatedFlickrJson(BrowserView):

    """Makes two Flickr API calls and writes the number of related
    photos and URLs for the most viewed related photo from the Pleiades
    Places group to JSON like

    {"portrait": {
      "page": 
        "http://flickr.com/photos/27621672@N04/3734425631/in/pool-1876758@N22", 
       "img": "http://farm3.staticflickr.com/2474/3734425631_b15979f2cd_m.jpg", 
       "title": "Pont d'Ambroix by sgillies" }, 
     "related": {
       "url": ["http://www.flickr.com/photos/tags/pleiades:*=149492/"], 
       "total": 2 }}

    for use in the Flickr Photos portlet on every Pleiades place page.
    """

    @ram.cache(_flickr_cache_key)
    def _get_related_photos(self, pid):
        # Count of related photos
        q = dict(
            method="flickr.photos.search",
            api_key=FLICKR_API_KEY,
            machine_tags="pleiades:*=%s" % pid,
            format="json",
            nojsoncallback=1)

        start = time()
        try:
            resp = requests.get(FLICKR_API_ENDPOINT, params=q, timeout=(2, 5))
        except requests.exceptions.RequestException:
            log.exception('Error making Flickr request for {}'.format(pid))
            raise FlickrResponseError(500)

        log.info('Flickr related request for pid {} took {} seconds'.format(
            pid, time() - start))

        if resp.status_code == 200:
            return resp.json()

        log.warn('Bad related Flickr data for pid {}, response code {}'.format(
            pid, resp.status_code))
        raise FlickrResponseError(resp.status_code)

    @ram.cache(_flickr_cache_key)
    def _get_pool_photos(self, pid):
        # Get portrait photo from group pool
        q = dict(
            method="flickr.groups.pools.getPhotos",
            api_key=FLICKR_API_KEY,
            group_id=PLEIADES_PLACES_ID,
            extras="views",
            format="json",
            nojsoncallback=1)

        if pid != "*":
            q['tags'] = "pleiades:depicts=" + pid

        start = time()
        try:
            resp = requests.get(FLICKR_API_ENDPOINT, params=q, timeout=(2, 5))
        except requests.exceptions.RequestException:
            log.exception('Error making Flickr pool request for {}'.format(
                pid))
            raise FlickrResponseError(500)

        log.info('Flickr pool request for pid {} took {} seconds'.format(
            pid, time() - start))

        if resp.status_code == 200:
            return resp.json()

        log.warn('Bad Flickr pool data for pid {}, response code {}'.format(
            pid, resp.status_code))
        raise FlickrResponseError(resp.status_code)

    def __call__(self, **kw):
        data = {}
        context = self.context

        if IPlace.providedBy(context):
            pid = context.getId()  # local id like "149492"
        elif ILocation.providedBy(context) or IName.providedBy(context):
            pid = aq_parent(aq_inner(context)).getId()
        else:
            pid = "*"

        tag = "pleiades:*=" + pid
        try:
            related = self._get_related_photos(pid)
        except FlickrResponseError:
            related = {}

        if related:
            total = 0
            photos = related.get('photos')
            if photos:
                total = int(photos['total'])

            data['related'] = dict(total=total, url=FLICKR_TAGS_BASE + tag)

        try:
            pool = self._get_pool_photos(pid)
        except FlickrResponseError as e:
            pool = {}
            self.request.response.setStatus(e.message)

        if pool:
            total = 0
            photos = pool.get('photos')
            if photos:
                total = int(photos['total'])
            if total < 1:
                data['portrait'] = None
            else:
                # Sort found photos by number of views, descending
                most_viewed = sorted(
                    photos['photo'], key=lambda p: p['views'], reverse=True )
                if pid == "*":
                    photo = choice(most_viewed)
                else:
                    photo = most_viewed[0]

                title = "%s by %s." % (
                    photo['title'].rstrip(" ."), photo['ownername'] )
                data['portrait'] = dict(
                    title=title, img=IMG_TMPL % photo, page=PAGE_TMPL % photo )

        self.request.response.setHeader('Content-Type', 'application/json')
        return simplejson.dumps(data)
