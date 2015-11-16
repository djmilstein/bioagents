import sys
import operator
from jnius import autoclass, cast
from TripsModule import trips_module

# Declare KQML java classes
KQMLPerformative = autoclass('TRIPS.KQML.KQMLPerformative')
KQMLList = autoclass('TRIPS.KQML.KQMLList')
KQMLObject = autoclass('TRIPS.KQML.KQMLObject')

from bioagents.dtda import DTDA

class DTDA_Module(trips_module.TripsModule):
    '''
    The DTDA module is a TRIPS module built around the DTDA agent. Its role is to
    receive and decode messages and send responses from and to other agents in 
    the system.
    '''
    def __init__(self, argv):
        # Call the constructor of TripsModule
        super(DTDA_Module, self).__init__(argv)
        # Instantiate a singleton DTDA agent
        self.tasks = ['is-drug-target', 'find-target-drug', 
                    'find-disease-targets', 'find-treatment']

    def init(self):
        '''
        Initialize TRIPS module
        '''
        super(DTDA_Module, self).init()
        # Send subscribe messages
        for task in self.tasks:
            task_str = 'ONT::%s' % task.upper()
            msg_txt = '(subscribe :content (request &key :content (%s . *)))' % task_str
            self.send(KQMLPerformative.fromString(msg_txt))
        self.dtda = DTDA()
        self.ready()

    def receive_request(self, msg, content):
        '''
        If a "request" message is received, decode the task and the content
        and call the appropriate function to prepare the response. A reply 
        "tell" message is then sent back.
        '''
        content_list = cast(KQMLList, content)
        task = content_list.get(0).toString().upper()
        sender = msg.getParameter(":sender")
        if task == 'ONT::IS-DRUG-TARGET':
            reply_content = self.respond_is_drug_target(content_list)
        elif task == 'ONT::FIND-TARGET-DRUG':
            reply_content = self.respond_find_target_drug(content_list)
        elif task == 'ONT::FIND-DISEASE-TARGETS':
            reply_content = self.respond_find_disease_targets(content_list)
        elif task == 'ONT::FIND-TREATMENT':
            reply_content = self.respond_find_treatment(content_list)
        else:
            self.error_reply(msg, 'unknown request task ' + task)
            return
        
        reply_msg = KQMLPerformative('reply')
        reply_msg.setParameter(':content', cast(KQMLObject, reply_content))
        self.reply(msg, reply_msg)
    
    def respond_is_drug_target(self, content_list):
        '''
        Response content to is-drug-target request
        '''
        # TODO: get parameters from content
        is_target = self.dtda.is_nominal_drug_target('Vemurafenib', 'BRAF')
        reply_content = KQMLList()
        if is_target:
            msg_str = 'TRUE'
        else:
            msg_str = 'FALSE'
        reply_content.add(msg_str)
        return reply_content
    
    def respond_find_target_drug(self, content_list):
        '''
        Response content to find-target-drug request
        '''
        # TODO: implement
        reply_content = KQMLList()
        reply_content.add('')
        return reply_content
    
    def respond_find_disease_targets(self, content_list):
        '''
        Response content to find-disease-targets request
        '''
        # TODO: implement
        self.dtda.get_mutation_statistics('pancreatic', 'missense')
        reply_content = KQMLList()
        reply_content.add('')
        return reply_content

    def respond_find_treatment(self, content_list):
        '''
        Response content to find-treatment request
        '''
        reply_content = KQMLList()
        
        # Parse content
        disease_str = content_list.getKeywordArg(':disease')
        if disease_str is None:
            print 'no disease set'
            reply_content.add('')
            return reply_content
        disease_str = disease_str.toString()
        disease_terms = disease_str[1:-1].split(' ')
        disease = disease_terms[0]
        disease_type = disease_terms[1]
        if disease.upper() != 'ONT::CANCER':
            print 'problem with disease name'
            reply_content.add('')
            return reply_content
        disease_type_filter = disease_type[5:].lower()
        
        # First, look for possible disease targets
        mutation_stats = self.dtda.get_mutation_statistics(disease_type_filter, 'missense')
        if mutation_stats is None:
            print 'no mutation stats'
            reply_content.add('')
            return reply_content
        # Return the top mutation as a possible target
        mutations_sorted = sorted(mutation_stats.items(), 
            key=operator.itemgetter(1), reverse=True)
        top_mutation = mutations_sorted[0]
        mut_protein = top_mutation[0]
        mut_percent = int(top_mutation[1][0]*100.0)

        reply_content = KQMLList.fromString('(ONT::PROPORTION :REFSET (ONT::CANCER-PATIENT) :QUAN (ONT::PERCENT %d) :CONTENT (ONT::MUTATION :AFFECTED ONT::%s))' % (mut_percent, mut_protein))
        return reply_content

if __name__ == "__main__":
    dm = DTDA_Module(['-name', 'DTDA'] + sys.argv[1:])
    dm.run()

