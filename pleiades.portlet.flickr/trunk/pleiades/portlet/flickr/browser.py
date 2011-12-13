import logging
from urllib import urlencode

import httplib2
import simplejson

from plone.memoize.instance import memoize
from Products.CMFCore.utils import getToolByName
from zope.interface import implements, Interface, Attribute
from zope.publisher.browser import BrowserPage, BrowserView

log = logging.getLogger("pleiades.portlet.flickr")

FLICKR_API_ENDPOINT = "http://api.flickr.com/services/rest/"
FLICKR_API_KEY = "b5899a9f7069f933b46b32b949ab4afd"
FLICKR_TAGS_BASE = "http://www.flickr.com/photos/tags/"

class RelatedFlickrJson(BrowserView):

    def __call__(self, **kw):
        data = {}
        # Search photos
        h = httplib2.Http()
        q = dict(
            method="flickr.photos.search",
            api_key=FLICKR_API_KEY,
            machine_tags="pleiades:*=%s" % self.context.getId(),
            format="json",
            nojsoncallback=1 )
        resp, content = h.request(FLICKR_API_ENDPOINT + "?" + urlencode(q), "GET")
        log.debug("Response: %s", resp)
        log.debug("Content: %s", content)
        if resp['status'] == "200":
            total = 0
            photos = simplejson.loads(content).get("photos")
            if photos:
                total = int(photos["total"])
            url = FLICKR_TAGS_BASE + "pleiades:*=%s/" % self.context.getId(),
            data['related'] = dict(total=total, url=url)
        
        # Get "portrait" from pool
        h = httplib2.Http()
        q = dict(
            method="flickr.groups.pools.getPhotos",
            api_key=FLICKR_API_KEY,
            group_id="1876758@N22",
            tags="pleiades:depicts=%s" % self.context.getId(),
            format="json",
            nojsoncallback=1 )
        resp, content = h.request(FLICKR_API_ENDPOINT + "?" + urlencode(q), "GET")
        log.debug("Response: %s", resp)
        log.debug("Content: %s", content)
        if resp['status'] == "200":
            total = 0
            photos = simplejson.loads(content).get("photos")
            if photos:
                total = int(photos["total"])
            if total < 1:
                data["portrait"] = None
            else:
                photo = photos["photo"][0]
                img = "http://farm%(farm)s.staticflickr.com/%(server)s/%(id)s_%(secret)s_m.jpg" % photo
                page = "http://flickr.com/photos/%(owner)s/%(id)s/in/pool-1876758@N22" % photo
                title = photo["title"] + " by " + photo["ownername"]
                data["portrait"] = dict(title=title, img=img, page=page)
        self.request.response.setStatus(200)
        self.request.response.setHeader('Content-Type', 'application/json')
        return simplejson.dumps(data)

