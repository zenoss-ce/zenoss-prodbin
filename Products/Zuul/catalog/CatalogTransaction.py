##############################################################################
# 
# Copyright (C) Zenoss, Inc. 2012, all rights reserved.
# 
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
# 
##############################################################################


import logging
from zope.interface import implements
import transaction
from transaction.interfaces import (ISavepointDataManager,
                                    IDataManagerSavepoint,
                                    ISynchronizer)
from .index_service import WebSocketCatalogService
from Products.Zuul.catalog.global_catalog import globalCatalogId
from uuid import uuid4

log = logging.getLogger('zen.catalogservice')

class CatalogServiceSynchronizer(object):
    implements(ISynchronizer)

    def __init__(self):
        self._service = WebSocketCatalogService(globalCatalogId)

    def beforeCompletion(self, tx):
        pass

    def afterCompletion(self, tx):
        # We can't rely on newTransaction being called (most code doesn't use
        # transaction.begin() to start a new transaction). Call it explicitly
        # after the current transaction exits.
        ws = getattr(tx, '_catalog_websocket', None)
        newtx = transaction.begin()
        setattr(newtx, '_transaction_id', str(uuid4()))
        if ws is not None and ws.connected and not getattr(
            tx, '_bad_websocket', False):
            delattr(tx, '_catalog_websocket')
            setattr(newtx, '_catalog_websocket', ws);
        self.newTransaction(newtx)

    def newTransaction(self, tx):
        pass


class TransactionSavepoint(object):
    """
    Implementation of savepoints for catalog service. These maintain a record
    of a unique savepoint id (as assigned in savepoint()) and allow rolling
    back to a defined savepoint.
    """
    implements(IDataManagerSavepoint)

    def __init__(self, svc, savepoint_id):
        self.catalog_service = svc
        self.savepoint_id = savepoint_id

    def rollback(self):
        # TODO: Need to determine a way to delete savepoints after this one
        # to clean up any resources in CatalogService.
        self.catalog_service.rollbackSavepoint(self.savepoint_id)


class TransactionManager(object):
    """
    Keeps track of which objects have been cataloged or uncatalogued in our
    current transaction. This keeps track of which objects
    have been cataloged and uncataloged. It is sync'ed with the server
    everytime there is a transaction committed.

    """
    implements(ISavepointDataManager)

    def __init__(self, txnmgr, svc):
        self.transaction_manager = txnmgr
        self.catalog_service = svc
        self._token = None
        self.modified_objects = 0

    def savepoint(self):
        savepoint_id = str(uuid4())
        self.catalog_service.createSavepoint(savepoint_id)
        return TransactionSavepoint(self.catalog_service, savepoint_id)

    def getToken(self):
        return self._token

    def setToken(self, token):
        self._token = token

    def abort(self, transaction):
        """Abort a transaction and forget all changes.

        Abort must be called outside of a two-phase commit.

        Abort is called by the transaction manager to abort transactions
        that are not yet in a two-phase commit.
        """
        if self._token is not None:
            self.catalog_service.abort(self._token)

    def tpc_begin(self, transaction):
        """Begin commit of a transaction, starting the two-phase commit.

        transaction is the ITransaction instance associated with the
        transaction being committed.
        """
        # Nothing to do here

    def commit(self, transaction):
        """Commit modifications to registered objects.

        Save changes to be made persistent if the transaction commits (if
        tpc_finish is called later).  If tpc_abort is called later, changes
        must not persist.

        This includes conflict detection and handling.  If no conflicts or
        errors occur, the data manager should be prepared to make the
        changes persist when tpc_finish is called.
        """
        if self._token is not None:
            self.catalog_service.commit(self._token)

    def tpc_finish(self, transaction):
        """Indicate confirmation that the transaction is done.

        Make all changes to objects modified by this transaction persist.

        transaction is the ITransaction instance associated with the
        transaction being committed.

        This should never fail.  If this raises an exception, the
        database is not expected to maintain consistency; it's a
        serious error.
        """
        # Nothing to do here

    def tpc_vote(self, transaction):
        """Verify that a data manager can commit the transaction.

        This is the last chance for a data manager to vote 'no'.  A
        data manager votes 'no' by raising an exception.

        transaction is the ITransaction instance associated with the
        transaction being committed.
        """
        if self._token is not None:
            if self.modified_objects:
                log.debug("Committing transaction - %d modified objects",
                          self.modified_objects)
                self.catalog_service.vote(self._token)
            else:
                log.debug("Aborting catalog transaction - no modifications")
                try:
                    self.catalog_service.abort(self._token)
                except Exception:
                    log.exception("Failed to abort transaction")

    def tpc_abort(self, transaction):
        """Abort a transaction.

        This is called by a transaction manager to end a two-phase commit on
        the data manager.  Abandon all changes to objects modified by this
        transaction.

        transaction is the ITransaction instance associated with the
        transaction being committed.

        This should never fail.
        """
        if self._token is not None:
            try:
                self.catalog_service.abort(self._token)
            except Exception:
                log.exception("Failed to abort")

    def sortKey(self):
        """Return a key to use for ordering registered DataManagers.
        """
        # this data manager must always go last
        return "~~~~~~~~~~~~~~~~~"


class WebSocketTransactionManager(TransactionManager):

    def commit(self, transaction):
        self.catalog_service.commit()

    def tpc_vote(self, transaction):
        self.catalog_service.vote()

    def tpc_abort(self, transaction):
        self.catalog_service.abort()

    def abort(self, transaction):
        # TODO: Do we need this?
        self.catalog_service.abort()


_SYNCHRONIZER = None


def registerSynchronizer(event):
    global _SYNCHRONIZER
    if not _SYNCHRONIZER:
        _SYNCHRONIZER = CatalogServiceSynchronizer()
        import transaction
        # Register with the current transaction
        try:
            _SYNCHRONIZER.newTransaction(transaction.get())
        except Exception as e:
            log.warning("Failed to register initial transaction with synchronizer: %s", e)
        # Register to be notified of new transactions
        transaction.manager.registerSynch(_SYNCHRONIZER)
