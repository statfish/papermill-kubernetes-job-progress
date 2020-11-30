# =================================================================
#
# Authors: Bernhard Mallinger <bernhard.mallinger@eox.at>
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


import os

from kubernetes import client as k8s_client, config as k8s_config
from papermill.engines import NBClientEngine


class KubernetesJobProgressEngine(NBClientEngine):
    @classmethod
    def execute_managed_notebook(cls, nb_man, *args, **kwargs):

        k8s_config.load_incluster_config()
        batch_v1 = k8s_client.BatchV1Api()

        job_name = os.environ["JOB_NAME"]
        progress_annotation = os.environ["PROGRESS_ANNOTATION"]
        namespace = current_namespace()

        orig_cell_complete = nb_man.cell_complete

        def patched_cell_complete(cell, cell_index, **kwargs):
            orig_cell_complete(cell, cell_index, **kwargs)

            ratio_progress = (cell_index + 1) / len(nb_man.nb.cells)
            # progress is a value between 0 and 100
            progress = round(ratio_progress * 100)

            batch_v1.patch_namespaced_job(
                job_name,
                namespace,
                {
                    "metadata": {
                        "annotations": {
                            progress_annotation: str(progress),
                        }
                    }
                },
            )

        nb_man.cell_complete = patched_cell_complete

        return super().execute_managed_notebook(nb_man, *args, **kwargs)


def current_namespace():
    # getting the current namespace like this is documented, so it should be fine:
    # https://kubernetes.io/docs/tasks/access-application-cluster/access-cluster/
    return open("/var/run/secrets/kubernetes.io/serviceaccount/namespace").read()
