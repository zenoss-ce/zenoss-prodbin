import re
import time
import socket
import logging
import json
from random import randint
from urlparse import urlparse
from functools import wraps

import transaction
from Products.AdvancedQuery import Eq, Or, And, Not, In, MatchRegexp, Between
from Products.AdvancedQuery import Ge, Le, MatchGlob, Generic

from Products.ZenUtils.websocket import ABNF, WebSocketException, WebSocket
from Products.ZenUtils.websocket import WebSocketConnectionClosedException
from Products.ZenUtils.GlobalConfig import getGlobalConfiguration


log = logging.getLogger('zen.index-service')


CATALOGTXATTR = '_catalog_transaction'
PROP_ZENCATALOGSERVICE_URI = 'zencatalogservice-uri'
POSSIBLE_DISCONNECTION_TIMEOUT = 290 # seconds
DEFAULT_ZENCATALOGSERVICE_URI = 'http://127.0.0.1:8553'


class CatalogServiceException(Exception):

    http_response_code = None
    http_response_msg = None

    def __init__(self, msg, http_response_code=None, http_response_msg=None):
        super(CatalogServiceException, self).__init__(msg)
        self.http_response_code = http_response_code
        self.http_response_msg = http_response_msg


class IndexAPIRequest(object):

    NOOP = "NOOP"
    TX_VOTE = "TX_VOTE"
    TX_ABORT = "TX_ABORT"
    TX_COMMIT = "TX_COMMIT"
    TX_FINISH = "TX_FINISH"
    SP_CREATE = "SP_CREATE"
    SP_DELETE = "SP_DELETE"
    SP_ROLLBACK = "SP_ROLLBACK"

    indexRequests = None
    txid = None
    query = None
    operation = None

    def __init__(self):
        self.indexRequests = []
        self.txid = "abc"
        self.query = None
        self.operation = self.NOOP

    def to_dict(self):
        d = {
            'txid': self.txid,
            'operation': self.operation
        }
        if self.indexRequests:
            d['indexRequests'] = [r.to_dict() for r in self.indexRequests]
        if self.query:
            d['query'] = self.query
        return d


class IndexRequest(object):

    ADD = "ADD"
    REMOVE = "REMOVE"

    operation = None
    states = None

    def __init__(self):
        self.states = []
        self.operation = None

    def new_datum(self):
        datum = ObjectData()
        self.states.append(datum)
        return datum

    def to_dict(self):
        return {
            'states': [s.to_dict() for s in self.states],
            'operation': self.operation
        }


class ObjectData(object):

    id_ = None
    version = None
    properties = None

    def __init__(self):
        self.id_ = None
        self.version = None
        self.properties = {}

    def to_dict(self):
        return {
            'id': self.id_,
            'version': self.version,
            'properties': self.properties
        }


class IndexAPIResponse(object):
    pass


def handleWebSocketException(f):
    @wraps(f)
    def inner(*args, **kwargs):
        try:
            result = f(*args, **kwargs)
        except WebSocketException as e:
            tx = transaction.get()
            tx._bad_websocket = True
            raise CatalogServiceException(e)
        return result
    return inner


class AggregatingWebSocket(WebSocket):

    def connect(self, *args, **kwargs):
        result = super(AggregatingWebSocket, self).connect(*args, **kwargs)
        if self.connected:
            self._last_frame_received_at = time.time()
        return result

    def recv_frame(self, *args, **kwargs):
        result = super(AggregatingWebSocket, self).recv_frame(*args, **kwargs)
        self._last_frame_received_at =time.time()
        return result

    def possibly_disconnected(self):
        last = getattr(self, '_last_frame_received_at', None)
        return last is None or last + POSSIBLE_DISCONNECTION_TIMEOUT < time.time()

    def ping_pong(self):
        """
        Sends a "ping", and then receives all frames until it gets the pong.
        """
        token = "%012x:%08x" % (int(round(time.time() * 1000)), randint(0, 2**32-1))
        self.ping(token)
        while True:
            frame = self.recv_frame()
            if not frame:
                raise WebSocketException("Received invalid websocket frame")
            elif frame.opcode == ABNF.OPCODE_PONG:
                if frame.data == token:
                    return True
            elif frame.opcode == ABNF.OPCODE_PING:
                self.pong(frame.data)
            elif frame.opcode == ABNF.OPCODE_CLOSE:
                self.send_close()
                raise WebSocketConnectionClosedException()
            else:
                pass # Discard. Perhaps too cavalier?

    def recv_all(self):
        """
        Performs the same actions as websocket.recv_data, but aggregates
        chunked messages.
        """
        result = []

        while True:
            frame = self.recv_frame()
            if not frame:
                # handle error:
                # 'NoneType' object has no attribute 'opcode'
                raise WebSocketException("Received invalid websocket frame")
            elif frame.opcode in (ABNF.OPCODE_TEXT, ABNF.OPCODE_BINARY) or (frame.opcode == 0 and result):
                result.append(frame.data)
                if frame.fin:
                    break
            elif frame.opcode == ABNF.OPCODE_CLOSE:
                self.send_close()
                raise WebSocketConnectionClosedException()
            elif frame.opcode == ABNF.OPCODE_PING:
                self.pong(frame.data)

        return ''.join(result)


def create_connection(url, timeout=None, **options):
    """
    copied from websocket.py; set timeout None if not specified
    """
    sockopt = options.get("sockopt", ())
    websock = AggregatingWebSocket(sockopt=sockopt)
    websock.settimeout(timeout)
    websock.connect(url, **options)
    return websock


class WebSocketCatalogService(object):

    TX_WEBSOCKET_ATTR = '_catalog_websocket'

    def __init__(self, catalog_id):
        config = getGlobalConfiguration()
        http_uri = config.get(PROP_ZENCATALOGSERVICE_URI,
                              DEFAULT_ZENCATALOGSERVICE_URI)
        # TODO: Reference the proxy
        self.uri = 'ws://{netloc}{path}/ws/index/global_catalog'.format(
            **urlparse(http_uri)._asdict())

    def connect(self):
        return create_connection(self.uri)

    @property
    def socket(self):
        tx = transaction.get()
        ws = getattr(tx, self.TX_WEBSOCKET_ATTR, None)
        if ws is None:
            ws = self.connect()
            setattr(tx, self.TX_WEBSOCKET_ATTR, ws)
        elif not ws.connected:
            raise CatalogServiceException("Connection was closed on the other side")
        return ws

    def reconnect_socket(self):
        tx = transaction.get()
        ws = getattr(tx, self.TX_WEBSOCKET_ATTR, None)
        if ws is None or not ws.connected:
            ws = self.connect()
            setattr(tx, self.TX_WEBSOCKET_ATTR, ws)
        if ws.possibly_disconnected():
            try:
                ws.ping_pong()
            except WebSocketConnectionClosedException:
                log.debug("Ping/Pong detected disconnection. Reconnecting!")
                ws = self.connect()
                setattr(tx, self.TX_WEBSOCKET_ATTR, ws)
                assert not ws.possibly_disconnected()
        return ws

    def _clearsocket(self):
        pass

    def _getCurrentCatalogTransaction(self):
        tx = transaction.get()
        mgr = getattr(tx, CATALOGTXATTR, None)
        if mgr is None:
            # Circular import
            from .CatalogTransaction import WebSocketTransactionManager
            mgr = WebSocketTransactionManager(tx, self)
            setattr(tx, CATALOGTXATTR, mgr)
            tx.join(mgr)
        return mgr

    def _get_response(self, txid):
        received_txid = None
        response = None
        # In case of weird empty messages from the other side,
        # drop any that are buffered up that don't correspond to
        # the current transaction.
        while txid != received_txid:
            result = self.socket.recv_all()
            response = json.loads(result)
            received_txid = response.get('txid')
        return response

    def _send(self, query=None, indexreq=None, op=IndexAPIRequest.NOOP, savepoint=None):
        newmsg = IndexAPIRequest()
        txid = getattr(transaction.get(), '_transaction_id', '')
        newmsg.operation = op
        newmsg.txid = txid
        if query is not None:
            newmsg.query = json.dumps(query)  # Expecting a JSON string, so double-serialize
        if indexreq is not None:
            newmsg.indexRequests.append(indexreq)
        if savepoint:
            pass
            ## Savepoints aren't supported yet
            # newmsg[savepointid = savepoint
        try:
            sock = self.socket
            if self._getCurrentCatalogTransaction().modified_objects == 0:
                sock = self.reconnect_socket()
            msgdict = newmsg.to_dict()
            log.debug("Sending message: %s", msgdict)
            sock.send(json.dumps(msgdict))
            response = self._get_response(txid)
        except socket.error:
            raise WebSocketConnectionClosedException()
        else:
            if response.get('exception'):
                raise CatalogServiceException(response['exception'])
            return response

    def abort(self):
        try:
            log.debug("Aborting current transaction via WebSocket")
            self._send(op=IndexAPIRequest.TX_ABORT)
            self._clearsocket()
        except WebSocketException:
            # Just let the transaction abort. The other side will
            # have to close the transaction on its own.
            pass

    @handleWebSocketException
    def commit(self):
        log.debug("Committing current transaction via WebSocket")
        self._send(op=IndexAPIRequest.TX_COMMIT)

    @handleWebSocketException
    def vote(self):
        log.debug("Voting on current transaction via WebSocket")
        self._send(op=IndexAPIRequest.TX_VOTE)
        self._clearsocket()

    @handleWebSocketException
    def createSavepoint(self, savepoint_id):
        log.debug("Creating savepoint via WebSocket")
        self._send(op=IndexAPIRequest.SP_CREATE, savepoint=savepoint_id)

    @handleWebSocketException
    def deleteSavepoint(self, savepoint_id):
        log.debug("Deleting savepoint via WebSocket")
        self._send(op=IndexAPIRequest.SP_DELETE, savepoint=savepoint_id)

    @handleWebSocketException
    def rollbackSavepoint(self, savepoint_id):
        log.debug("Rolling back to savepoint via WebSocket")
        self._send(op=IndexAPIRequest.SP_ROLLBACK, savepoint=savepoint_id)

    @handleWebSocketException
    def index_object(self, request):
        self._execute_batch_request(request)

    @handleWebSocketException
    def unindex_object(self, request):
        self._execute_batch_request(request)

    @handleWebSocketException
    def search(self, query):
        log.debug("Searching via WebSocket")
        response = self._send(query=query)
        if len(response.get('results', ())):
            return tuple(response['results']), len(response['results'])
        return (), 0

    @handleWebSocketException
    def _execute_batch_request(self, request):
        log.debug("Executing catalog request via WebSocket")
        txmgr = self._getCurrentCatalogTransaction()
        # TODO: version and stuff
        self._send(indexreq=request)

        # We keep track of the number of modified objects in a transaction
        # in order to determine whether it's safe to just reset the websocket
        # connection if it goes down.
        modified_objects = len(request.states)
        if modified_objects:
            txmgr.modified_objects += modified_objects


class AdvancedQueryToElastic(object):

    _PREFIX_PATTERN = re.compile(r"^[^\*\?]+\*+$")

    def _isRegexish(self, term):
        """
        We generally use glob matching for performance and a better user
        experience but if the query has regex characters in it then make it
        a regex object
        """
        value = term.replace("(?i)", "")
        return  "["  in value or "(" in value or "|" in value

    def _convert_Eq(self, query):
        return {"term": {query._idx: query._term}}

    def _convert_And(self, query):
        return {"and": map(self._convert, query._subqueries)}

    def _convert_Or(self, query):
        return {"or": map(self._convert, query._subqueries)}

    def _convert_In(self, query):
        return {"in": {query._idx: query._term}}

    def _convert_MatchRegexp(self, query):
        term = query._term
        if self._isRegexish(term):
            return {"regexp": {query._idx: term}}
        else:
            term = term.replace("(?i)", "").replace(".*", "*")
            return self._convert(MatchGlob(query._idx, term))

    def _convert_Between(self, query):
        from_, to_ = query._term
        return {"range": {
            query._idx: {
                "from": from_,
                "to": to_,
                "include_lower": True,
                "include_upper": True
            }
        }}

    def _convert_Ge(self, query):
        return {"range": {
            query._idx: {
                "gte": query._term
            }
        }}

    def _convert_Le(self, query):
        return {"range": {
            query._idx: {
                "lte": query._term
            }
        }}

    def _convert_Not(self, query):
        return {"not": {"filter":
            self._convert(query._query)
        }}

    def _convert_MatchGlob(self, query):
        term = query._term
        if self._PREFIX_PATTERN.match(term):
            return {
                "prefix": {
                    query._idx: term.rstrip("*")
                }
            }
        else:
            return {
                "wildcard": {
                    query._idx: term
                }
            }

    def _convert_Generic(self, query):
        # We only support path queries
        assert query._idx == "path"
        return {"in": {query._idx: query._term["query"]}}


    FUNCTORS = {
        Eq: _convert_Eq,
        In: _convert_In,
        MatchRegexp: _convert_MatchRegexp,
        Between: _convert_Between,
        Ge: _convert_Ge,
        Le: _convert_Le,
        MatchGlob: _convert_MatchGlob,
        Generic: _convert_Generic,
        And: _convert_And,
        Or: _convert_Or,
        Not: _convert_Not,
    }

    def _convert(self, query):
        functor = self.FUNCTORS[query.__class__]
        return functor.__get__(self, None)(query)

    def convert(self, query):
        return {
            #"query": {
                "constant_score": {
                    "filter": self._convert(query)
                }
            #}
        }
