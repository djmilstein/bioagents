"""Web API client for a Kappa simulator."""

import json
import os
import re
import requests
import pickle
from datetime import datetime
from time import sleep


KAPPA_BASE = 'https://api.executableknowledge.org/kappa/v2'


class KappaRuntimeError(Exception):
    def __init__(self, resp):
        self.error = resp.reason
        self.text = re.findall(
            'u?[\"\']text[\"\']: ?u?[\"\'](.*?)[\"\'],',
            resp.content
            )
        try:
            now = datetime.now()
            pkl_name = '%s_err_resp.pkl' % now.strftime('%Y%m%d-%H%M%S')
            with open(pkl_name, 'wb') as f:
                pickle.dump(resp, f, protocol=2)
            print("Pickled response for further analysis.")
            print("See %s" % os.path.abspath(pkl_name))
        except Exception:
            print("Failed to pickle response for further analysis.")
        return

    def __str__(self):
        msg = "Kappa failed with error: %s." % self.error
        if self.text:
            msg += "\nThe following text was found: %s." % ', '.join(self.text)
        return msg


class KappaRuntime(object):
    kappa_url = KAPPA_BASE + '/projects'

    def __init__(self, project_name='default'):
        """Create a Kappa client."""
        self.project_name = self.check_name(project_name)
        self.url = self.kappa_url + '/' + self.project_name
        self.start_project()
        return

    def __del__(self):
        "Delete the project when you go"
        self.delete_project()
        return

    def get_project_list(self):
        """Get the list of projects on the kappa server."""
        resp = self.dispatch('get', self.kappa_url)
        if resp.status_code is not 200:
            raise KappaRuntimeError(resp)
        return resp.json()

    def check_name(self, proj_name):
        """Make sure the project name is unique."""
        if proj_name != 'default' and proj_name in self.get_project_list():
            name_fmt = proj_name + "_%d"
            i = 0
            times_confirmed = 0
            while times_confirmed < 2:
                if name_fmt % i not in self.get_project_list():
                    times_confirmed += 1
                    # Give any other tools a chance to make their project.
                    sleep(1)
                else:
                    i += 1
            proj_name = name_fmt % i
        return proj_name

    def start_project(self):
        """Method to recreate the project, removing anything that was there."""
        if self.project_name != 'default' or 'default' not in self.get_project_list():
            data = {'project_id': self.project_name}
            self.dispatch('post', self.kappa_url, data)
        return

    def delete_project(self):
        """delete_project the project."""
        if self.project_name != 'default':
            self.dispatch('delete_project', self.kappa_url + '/' + self.project_name)

    def reset_project(self):
        """reset_project the project."""
        self.delete_project()
        self.start_project()

    def dispatch(self, method, url, data=None):
        """Send a request of type method to the project."""
        if not hasattr(requests, method):
            raise AttributeError('Requests does not have method %s.' % method)
        if data is not None:
            data = json.dumps(data).encode('utf8')
        resp = getattr(requests, method)(url, data=data)
        if resp.status_code is not 200:
            raise KappaRuntimeError(resp)
        return resp

    def get_files(self):
        """Get a list of files in this project."""
        resp = self.dispatch('get', self.url + '/files')
        return [f['id'] for f in resp.json()]

    def add_file(self, fname):
        """Add a file to the project."""
        with open(fname, 'rb') as f:
            content = f.read()

        file_list = self.get_files()
        if fname in file_list:
            requests.delete(self.url + '/files/%s' % fname)

        return self.add_code(content, os.path.basename(fname))

    def add_code(self, code_str, name=None):
        """Add a code string to the project."""
        if name is None:
            fname_list = self.get_files()
            fmt = "bioagent_%d.ka"
            i = 0
            while fmt % i in fname_list:
                i += 1
            name = fmt % i
        file_data = {
            'metadata': {
                'compile': True,
                'id': name,
                'position': 0,
                'version': [{
                    'client_id': 'foobar',
                    'local_version_file_version': 0
                    }]
                },
            'content': code_str
            }
        self.dispatch('post', self.url + '/files', file_data)
        return

    def version(self):
        """Return the version of the Kappa environment."""
        res = self.dispatch('get', KAPPA_BASE)
        content = res.json()
        version = content.get('build')
        return version

    def compile(self, fname_list=None, code_list=None):
        """Parse given Kappa files and any other files that have been added.

        Parameters
        ----------
        fname_list : List or None
            A list of local file names (ending in `.ka`) to be added to the
            project before compiling. None by default, indicating no new files.
        code_list : List or None
            A list of code strings to be added to the project before compiling.
            None by default, indicating no new strings.
        """
        for fname in [] if fname_list is None else fname_list:
            self.add_file(fname)
        for code_str in [] if code_list is None else code_list:
            self.add_code(code_str)
        res = self.dispatch('post', self.url + '/parse', [])
        content = res.json()
        return content

    def start_sim(self, **parameters):
        """Start a simulation with given parameters.

        Note that parameters are subject to changes in the kappa remote api.

        Parameters
        ----------
        plot_period : int or float
            The time period between output (plot) points returned by the
            simulation. Default: 10
        pause_condition : string or None
            A Kappa Boolean expression defining a pause condition for the
            simulation. Default: None
        seed: int
            A random seed for the stochastic simulation. Default: None
        store_trace : bool
            Presumably you can choose whether to store the trace. Hopefully
            interpretation is straightforward. Default: True
        """
        complete_params = {
            'plot_period': 10,
            'pause_condition': '[false]',
            'seed': None,
            'store_trace': True
            }
        complete_params.update(parameters)
        resp = self.dispatch('post', self.url + '/simulation', complete_params)
        return resp.json()

    def _tell_sim(self, method, cmd):
        return self.dispatch(method, self.url + '/simulation/%s' % cmd)

    def pause_sim(self):
        """Pause a given simulation."""
        self._tell_sim('put', 'pause')

    def continue_sim(self):
        """Continue the pause simulation."""
        self._tell_sim('put', 'continue')

    def sim_status(self):
        """Return status of running simulation."""
        resp = self.dispatch('get', self.url + '/simulation')
        return json.loads(resp.content)

    def sim_plot(self):
        """Get the data from the simulation."""
        resp = self._tell_sim('get', 'plot')
        return json.loads(resp.content)
