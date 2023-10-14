# =================================================================
#
# Authors: Bernhard Mallinger <bernhard.mallinger@eox.at>
#          Dan Stieglitz <dstieglitz@stainless.ai>
#
# Copyright (C) 2020 EOX IT Services GmbH <https://eox.at>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================
import asyncio
import os

from nats.aio.client import Client as NATS
from papermill.engines import NBClientEngine
import json
from datetime import datetime
import threading

import logging

logger = logging.getLogger("papermill")


class KubernetesJobProgressEngine(NBClientEngine):
    print("Loaded KubernetesJobProgressEngine")
    nc = NATS()
    conn = None
    cell_start_timestamp = None
    progress_future = None
    nats_debug = None
    subject = "progress"
    notebook_id_key = "NOTEBOOK_ID"
    #
    # If the event loop is not started (somewhere)
    # messages will not be sent
    #
    loop = asyncio.new_event_loop()
    done = False

    try:
        notebook_id_key = os.environ['NOTEBOOK_ID_ENV_KEY']
    except KeyError as e:
        pass

    try:
        subject = os.environ['NATS_SUBJECT']
    except KeyError as e:
        pass

    notebook_id = os.environ[notebook_id_key]
    nats_url = os.environ['NATS_URL']
    nats_user = os.environ['NATS_USER']
    nats_password = os.environ['NATS_PASSWORD']

    try:
        nats_debug = os.environ['NATS_DEBUG']
        if nats_debug:
            os.environ['PYTHONASYNCIODEBUG'] = '1'
    except KeyError as e:
        pass

    @classmethod
    async def nats_connect(cls):
        print(f"nats_connect")
        if cls.nats_debug:
            print(f"Connecting to {cls.nats_url}...")
        await cls.nc.connect(cls.nats_url,
                             user=cls.nats_user,
                             password=cls.nats_password,
                             verbose=True)
        if cls.nats_debug:
            print(f"Connected to {cls.nats_url}")

    @classmethod
    async def nats_send(cls, cell_index, cell_count, start_time, end_time, duration, progress, type='progress'):
        print(f"nats_send {cell_index}")
        await cls.nats_connect()
        msg = {
            'notebook_id': cls.notebook_id,
            'timestamp': str(datetime.utcnow().isoformat()),
            'type': type,
            'cell_index': cell_index,
            'cell_count': cell_count,
            'start': start_time.isoformat(),
            'end': end_time.isoformat(),
            'duration': duration,
            'progress': progress
        }
        await cls.nc.publish(cls.subject, bytes(json.dumps(msg, default=str), 'utf-8'))
        if cls.nats_debug:
            print(f"sent {json.dumps(msg, default=str)}")

    @classmethod
    def run_loop(cls):
        cls.loop.run_forever()

    @classmethod
    def execute_managed_notebook(cls,
                                 nb_man,
                                 kernel_name,
                                 log_output=True,
                                 stdout_file=None,
                                 stderr_file=None,
                                 start_timeout=60,
                                 execution_timeout=None,
                                 **kwargs):

        print(f"execute_managed_notebook({kwargs})")
        orig_cell_complete = nb_man.cell_complete
        orig_cell_start = nb_man.cell_start
        orig_cell_exception = nb_man.cell_exception
        orig_notebook_complete = nb_man.notebook_complete

        def patched_notebook_complete(**kwargs):
            print(f"Patched notebook_complete")
            cls.loop.stop()
            orig_notebook_complete(**kwargs)

        def patched_cell_exception(cell, cell_index=None, **kwargs):
            print(f"Patched cell exception {cell_index}: {kwargs}")
            asyncio.run_coroutine_threadsafe(
                cls.nats_send(
                    cell_index,
                    -1,
                    datetime.now(),
                    datetime.now(),
                    -1,
                    -1,
                    type='error'),
                loop=cls.loop)
            orig_cell_exception(cell, cell_index, **kwargs)

        def patched_cell_start(cell, cell_index, **kwargs):
            print(f"Patched cell start {cell_index}")
            cls.cell_start_timestamp = datetime.utcnow()
            orig_cell_start(cell, cell_index, **kwargs)

        def patched_cell_complete(cell, cell_index, **kwargs):
            print(f"Patched cell complete {cell_index}")
            orig_cell_complete(cell, cell_index, **kwargs)

            ratio_progress = (cell_index + 1) / len(nb_man.nb.cells)
            # progress is a value between 0 and 100
            progress = round(ratio_progress * 100)
            print(f"Progress is {progress}%")
            cell_end_timestamp = datetime.utcnow()
            duration = cell_end_timestamp - cls.cell_start_timestamp
            print(f"Duration is  {duration}")
            progress_future = asyncio.run_coroutine_threadsafe(
                cls.nats_send(
                    cell_index,
                    len(nb_man.nb.cells),
                    cls.cell_start_timestamp,
                    cell_end_timestamp,
                    duration,
                    progress),
                loop=cls.loop)
            print(progress_future)
            if progress == 100:
                cls.loop.stop()

        nb_man.cell_complete = patched_cell_complete
        nb_man.cell_start = patched_cell_start
        nb_man.cell_exception = patched_cell_exception
        nb_man.notebook_complete = patched_notebook_complete

        # if cls.progress_future:
        #     asyncio.wait_for(cls.progress_future, 10)
        #     asyncio.ensure_future(cls.nc.close())

        print("Starting progress thread")
        threading.Thread(target=cls.run_loop, daemon=True).start()

        print(f"Calling super...")
        return super().execute_managed_notebook(nb_man,
                                                kernel_name,
                                                log_output=True,
                                                stdout_file=None,
                                                stderr_file=None,
                                                start_timeout=60,
                                                execution_timeout=None,
                                                **kwargs)
