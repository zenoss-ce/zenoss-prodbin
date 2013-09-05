##############################################################################
#
# Copyright (C) Zenoss, Inc. 2012, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################


import os
import time
from Products.ZCatalog.Catalog import Catalog as ZopeCatalog, CatalogSearchArgumentsMap
from Products.ZCatalog.Lazy import LazyCat, LazyMap
from Products.PluginIndexes.common import safe_callable
from .index_service import WebSocketCatalogService, CatalogServiceException
from Products.ZenUtils.websocket import WebSocketConnectionClosedException
#from .AdvancedQueryProtobufAdapter import AdvancedQueryProtobufAdapter, CatalogSearchArgumentsMapToProtobufAdapter
from ZenPacks.zenoss.CatalogService.protocols.catalogservice_pb2 import BatchRequest
#from .protocols import catalogservice_pb2 as enums
from Products.Zuul.catalog.global_catalog import globalCatalogId
import logging

log = logging.getLogger('zen.catalogservice')
LONG_QUERY_TIME = 1.0
_marker = []

class Catalog(ZopeCatalog):
    _v_catalogService = None

    def __init__(self, *args, **kwargs):

        self.initialized = False
        super(Catalog, self).__init__(*args, **kwargs)
        self.initialized = True

    def __getitem__(self, index, ttype=type(())):
        """
        Our search results protobuf has type long (for the java side) and
        the internal catalog structure expects an int.
        """
        if type(index) == long:
            index = int(index)
        return ZopeCatalog.__getitem__(self, index, ttype)

    def _get_service(self):
        if self._v_catalogService is None:
            self._v_catalogService = WebSocketCatalogService(globalCatalogId)
        return self._v_catalogService

    # Copied from PluginIndexes.common.UnIndex
    def _get_object_datum(self, obj, attr):
        # self.id is the name of the index, which is also the name of the
        # attribute we're interested in.  If the attribute is callable,
        # we'll do so.
        try:
            datum = getattr(obj, attr)
            if safe_callable(datum):
                datum = datum()
        except (AttributeError, TypeError):
            datum = _marker
        return datum

    def _addIndexedAttributes(self, catalogObject, attrs):
        """
        Accepts a key value set of values to be indexed
        on this protobuf and adds them.

        @type  catalogObject: Protobuf
        @param catalogObject: protobuf of the items we are cataloging
        @type  attrs: dict
        @param attrs: Key/value pair of values to add to this protobuf
        """
        # get the rest of the index values
        for name, value in attrs.iteritems():
            values = []
            if value is None:
                values.append("")
            # indexed values are always multiple (for keyword indexes)
            elif hasattr(value, "__iter__"):
                values.extend(filter(lambda v: v is not None, value))
            else:
                values.append(value)
            if values:
                idxValue = catalogObject.indexedvalues.add(name=name)
                for value in values:
                    try:
                        idxValue.values.append(value)
                    except (TypeError, ValueError):
                        try:
                            idxValue.values.append(unicode(value))
                        except UnicodeDecodeError:
                            log.error("Failed to append protobuf attr key:%s value:%s catalogObject:%s", name, value, catalogObject)
                            raise

    def clear(self):
        if self.initialized:
            try:
                self._get_service().clear()
            except CatalogServiceException as e:
                if e.http_response_code == 404 or isinstance(e.message, WebSocketConnectionClosedException):
                    log.debug("Ignoring error clearing a catalog which doesn't exist")
                else:
                    raise
    
        super(Catalog, self).clear()
         

    def fillCatalogRequest(self, catalogObject, uid, attrs):
        """
        Populates the BatchRequest for cataloging an object. Nothing
        is returned but the passed in protobuf is populated
        with the indexed values.

        @type  catalogObject: Protobuf
        @param catalogObject: protobuf of the item we are cataloging
        @type  uid: string
        @param uid: Unique path of the object
        @type  attrs: dict
        @param attrs: Key/Value of values to index
        """
        paths = set()
        paths.add(uid)

        if attrs.get('path'):
            # can specify multiple paths in the attributes
            for path in attrs['path']:
                if isinstance(path, basestring):
                    full_path = path
                else:
                    full_path = "/".join(path)
                paths.add(full_path)
        attrs['path'] = paths

        self._addIndexedAttributes(catalogObject, attrs)

    def catalogObject(self, object, uid, threshold=None, idxs=None,
                      update_metadata=1):
        index = self.uids.get(uid, None)

        if index is None:  # we are inserting new data
            index = self.updateMetadata(object, uid, None)
            self._length.change(1)
            self.uids[uid] = index
            self.paths[index] = uid

        elif update_metadata:  # we are updating and we need to update metadata
            self.updateMetadata(object, uid, index)

        # Always update all indexes - Lucene doesn't update individual fields
        use_indexes = self.indexes.keys()

        attrs = {}
        for name in use_indexes:
        # End copied from ZCatalog.Catalog
        # Begin custom code replacing Catalog indexing
            attrs[name] = self._get_object_datum(object, name)

        svc = self._get_service()

        # create the batch request protobuf
        request = BatchRequest()
        catalog = request.catalog.add(rid=index)
        self.fillCatalogRequest(catalog, uid, attrs)

        # Send the request
        svc.index_object(request)

    def uncatalogObject(self, uid):
        svc = self._get_service()

        # create a request protobuf
        if uid in self.uids:
            request = BatchRequest()
            request.uncatalog.append(self.uids[uid])

            svc.unindex_object(request)

        ZopeCatalog.uncatalogObject(self, uid)

    def make_query(self, query):
        if isinstance(query, CatalogSearchArgumentsMap):
            adapter = CatalogSearchArgumentsMapToProtobufAdapter()
            return adapter.makeProtobuf(query)
        else:
            adapter = AdvancedQueryProtobufAdapter()
            return adapter.advancedQueryToProtobuf(query)

    def search(self, query, sort_index=None, reverse=0, limit=None, merge=1, start=0):
        """
        Searches the catalog by issuing a request to the catalog service.
        @type  query: AdvancedQuery
        @param query: query for the objects we are searching for

        # Pagination objects
        @type  sort_index: string
        @param sort_index: indexfield we are searching upon
        @type  reverse: bool
        @param reverse: Truthy/Falsey values for if we are sorting in reverse or not
        @type  limit: int
        @param limit: Query limit
        @type  merge: bool
        @rtype:   LazyMap
        @return:  Search result of brains
        """
        # query has been transformed from an AdvancedQuery Object to a protobuf
        if isinstance(query, CatalogSearchArgumentsMap) and not query.keywords:
            starttime = time.time()
            rs = self.data.keys()
            total = len(rs)
        else:
            query = self.make_query(query)
            if limit is not None:
                query.limit = limit
            if start:
                query.start = start
            if sort_index:
                if not hasattr(sort_index, '__iter__'):
                    sort_index = (sort_index,)
                for sort in sort_index:
                    if isinstance(sort, (tuple, list)):
                        name, direction = sort
                        direction = enums.DESCENDING if direction.lower() == 'desc' else enums.ASCENDING
                        query.sort.add(name=name, direction=direction)
                    elif isinstance(sort, basestring):
                        query.sort.add(name=sort)
                    elif hasattr(sort, 'id'):
                        query.sort.add(name=sort.id)

            # query
            log.debug(str(query))
            starttime = time.time()
            svc = self._get_service()

            rs, total = svc.search(query)

        totalTime = time.time() - starttime
        # log if over a threshold
        if totalTime > LONG_QUERY_TIME:
            log.debug("Excessive time spent in service request %s for search %s", str(time.time() - starttime), query)
            log.debug("Records Returned: %d Total items %d", len(rs), total)

        if rs:
            num_rids = len(rs)
            # make sure we have a brain before returning the rid
            rs = [rid for rid in rs if int(rid) in self.data]
            # If we failed to find a brain for a returned rid, inform the
            # user to run a script to repair the inconsistency.
            if len(rs) != num_rids:
                if __file__:
                    script = os.path.join(os.path.dirname(__file__), 'sync_rids.py')
                else:
                    script = 'sync_rids.py'
                log.warn("Detected catalog inconsistency - to repair, run: 'python %s'",
                         script)
            result = LazyMap(self.__getitem__, rs, len(rs), actual_result_count=total)
        else:
            # Empty result set
            result = LazyCat([])
        return result
