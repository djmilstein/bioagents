import sys
import json
import logging
from bioagents import Bioagent
from kqml import KQMLList, KQMLString
from .qca import QCA
from indra.statements import stmts_from_json
from indra.assemblers import EnglishAssembler
from indra.sources.trips.processor import TripsProcessor


logging.basicConfig(format='%(levelname)s: %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('QCA')


class QCA_Module(Bioagent):
    '''
    The QCA module is a TRIPS module built around the QCA agent.
    Its role is to receive and decode messages and send responses from and
    to other agents in the system.
    '''
    name = 'QCA'
    tasks = ['FIND-QCA-PATH', 'HAS-QCA-PATH']

    def __init__(self, **kwargs):
        # Instantiate a singleton QCA agent
        self.qca = QCA()
        # Call the constructor of Bioagent
        super(QCA_Module, self).__init__(**kwargs)

    def respond_find_qca_path(self, content):
        """Response content to find-qca-path request"""
        if self.qca.ndex is None:
            reply = self.make_failure('SERVICE_UNAVAILABLE')
            return reply

        source_arg = content.gets('SOURCE')
        target_arg = content.gets('TARGET')
        reltype_arg = content.get('RELTYPE')

        if not source_arg:
            raise ValueError("Source list is empty")
        if not target_arg:
            raise ValueError("Target list is empty")

        target = self._get_term_name(target_arg)
        if target is None:
            reply = self.make_failure('NO_PATH_FOUND')
            # NOTE: use the one below if it's handled by NLG
            #reply = self.make_failure('TARGET_MISSING')
            return reply

        source = self._get_term_name(source_arg)
        if source is None:
            reply = self.make_failure('NO_PATH_FOUND')
            # NOTE: use the one below if it's handled by NLG
            #reply = self.make_failure('SOURCE_MISSING')
            return reply

        if reltype_arg is None or len(reltype_arg) == 0:
            relation_types = None
        else:
            relation_types = [str(k.data) for k in reltype_arg.data]

        results_list = self.qca.find_causal_path([source], [target],
                                                 relation_types=relation_types)
        if not results_list:
            reply = self.make_failure('NO_PATH_FOUND')
            return reply
        first_result = results_list[0]
        first_edges = first_result[1::2]
        indra_edges = [fe[0]['INDRA json'] for fe in first_edges]
        indra_edges = [json.loads(e) for e in indra_edges]
        indra_edges = _fix_indra_edges(indra_edges)
        indra_edge_stmts = stmts_from_json(indra_edges)
        for stmt in indra_edge_stmts:
            txt = EnglishAssembler([stmt]).make_model()
            self.send_provenance_for_stmts(
                [stmt], "the path from %s to %s (%s)" % (source, target, txt))
        indra_edges_str = json.dumps(indra_edges)
        ks = KQMLString(indra_edges_str)

        reply = KQMLList('SUCCESS')
        reply.set('paths', KQMLList([ks]))

        return reply

    def respond_has_qca_path(self, content):
        """Response content to find-qca-path request."""
        target_arg = content.gets('TARGET')
        source_arg = content.gets('SOURCE')
        reltype_arg = content.get('RELTYPE')

        if not source_arg:
            raise ValueError("Source list is empty")
        if not target_arg:
            raise ValueError("Target list is empty")

        target = self._get_term_name(target_arg)
        source = self._get_term_name(source_arg)

        if reltype_arg is None or len(reltype_arg) == 0:
            relation_types = None
        else:
            relation_types = [str(k.data) for k in reltype_arg.data]

        has_path = self.qca.has_path([source], [target])

        reply = KQMLList('SUCCESS')
        reply.set('haspath', 'TRUE' if has_path else 'FALSE')

        return reply

    def _get_term_name(self, term_str):
        tp = TripsProcessor(term_str)
        terms = tp.tree.findall('TERM')
        if not terms:
            return None
        term_id = terms[0].attrib['id']
        agent = tp._get_agent_by_id(term_id, None)
        if agent is None:
            return None
        return agent.name


def _fix_indra_edges(stmt_json_list):
    """Temporary fixes to latest INDRA representation."""
    for stmt in stmt_json_list:
        if stmt.get('type') == 'RasGef':
            stmt['type'] = 'Gef'
        if stmt.get('type') == 'RasGap':
            stmt['type'] = 'Gap'
    return stmt_json_list


if __name__ == "__main__":
    QCA_Module(argv=sys.argv[1:])
