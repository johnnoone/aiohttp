"""Tests for aiohttp/worker.py"""
import asyncio
import unittest
import unittest.mock

from aiohttp import worker
from aiohttp.wsgi import WSGIServerHttpProtocol


class TestWorker(worker.AsyncGunicornWorker):

    def __init__(self):
        self.connections = {}


class WorkerTests(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(None)
        self.worker = TestWorker()

    def tearDown(self):
        self.loop.close()

    @unittest.mock.patch('aiohttp.worker.asyncio')
    def test_init_process(self, m_asyncio):
        try:
            self.worker.init_process()
        except AttributeError:
            pass

        self.assertTrue(m_asyncio.get_event_loop.return_value.close.called)
        self.assertTrue(m_asyncio.new_event_loop.called)
        self.assertTrue(m_asyncio.set_event_loop.called)

    @unittest.mock.patch('aiohttp.worker.asyncio')
    def test_run(self, m_asyncio):
        self.worker.loop = unittest.mock.Mock()
        self.worker.run()

        self.assertTrue(m_asyncio.async.called)
        self.assertTrue(self.worker.loop.run_until_complete.called)
        self.assertTrue(self.worker.loop.close.called)

    def test_factory(self):
        self.worker.wsgi = unittest.mock.Mock()
        self.worker.loop = unittest.mock.Mock()
        self.worker.log = unittest.mock.Mock()
        self.worker.cfg = unittest.mock.Mock()

        f = self.worker.factory(
            self.worker.wsgi, 'localhost', 8080)
        self.assertIsInstance(f, WSGIServerHttpProtocol)

    @unittest.mock.patch('aiohttp.worker.asyncio')
    def test__run(self, m_asyncio):
        self.worker.ppid = 1
        self.worker.alive = True
        self.worker.servers = []
        sock = unittest.mock.Mock()
        sock.cfg_addr = ('localhost', 8080)
        self.worker.sockets = [sock]
        self.worker.wsgi = unittest.mock.Mock()
        self.worker.log = unittest.mock.Mock()
        self.worker.loop = unittest.mock.Mock()
        self.worker.notify = unittest.mock.Mock()

        self.loop.run_until_complete(self.worker._run())

        m_asyncio.async.return_value.add_done_callback.call_args[0][0](
            self.worker.sockets[0])

        self.assertTrue(self.worker.log.info.called)
        self.assertTrue(self.worker.notify.called)

    @unittest.mock.patch('aiohttp.worker.os')
    @unittest.mock.patch('aiohttp.worker.asyncio.sleep')
    def test__run_exc(self, m_sleep, m_os):
        m_os.getpid.return_value = 1
        m_os.getppid.return_value = 1

        self.worker.servers = [unittest.mock.Mock()]
        self.worker.ppid = 1
        self.worker.alive = True
        self.worker.sockets = []
        self.worker.log = unittest.mock.Mock()
        self.worker.loop = unittest.mock.Mock()
        self.worker.notify = unittest.mock.Mock()

        slp = asyncio.Future(loop=self.loop)
        slp.set_exception(KeyboardInterrupt)
        m_sleep.return_value = slp

        self.loop.run_until_complete(self.worker._run())
        self.assertTrue(m_sleep.called)
        self.assertTrue(self.worker.servers[0].close.called)

    def test_portmapper_worker(self):
        wsgi = {1: object(), 2: object()}
        
        class Worker(worker.PortMapperWorker):

            def __init__(self, wsgi):
                self.wsgi = wsgi

            def factory(self, wsgi, host, port):
                return wsgi

        w = Worker(wsgi)
        
        self.assertIs(
            wsgi[1], w.get_factory(object(), '', 1)())
        self.assertIs(
            wsgi[2], w.get_factory(object(), '', 2)())

    def test_wrp(self):
        tracking = {}
        meth = unittest.mock.Mock()
        wrp = worker._wrp(1, meth, tracking)
        wrp()

        self.assertIn(1, tracking)
        self.assertTrue(meth.called)

        meth = unittest.mock.Mock()
        wrp = worker._wrp(1, meth, tracking, False)
        wrp()

        self.assertNotIn(1, tracking)
        self.assertTrue(meth.called)