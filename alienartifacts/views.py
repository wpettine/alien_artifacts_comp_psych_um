from .functions import *
import json
import urllib
from django.http import JsonResponse, HttpResponse
from .models import Stimulus, Session, Subject, Trial, TutorialStimulus, RewardStimulus
from datetime import datetime
import numpy as np
import os, logging
from .global_variables import *

# Get an instance of a logger
logger = logging.getLogger('django')


def index(request):
    try:
        return consentform(request)
    except:
        logger.error(f'Something went wrong in the index function')


def health(request):
    try:
        return HttpResponse()
    except Exception as e:
        logger.error('Error in %s', 'consentformProlific', exc_info=e)

# Views

def consentform(request):
    if PROLIFIC:
        # Prolific pulls URL parameters, so we use a different consent form.
        return consentformProlific(request)
    else:
        # The standard one doesn't pull parameters from the URL
        return consentformStandard(request)


def consentformStandard(request):
    try:
        link_url = 'alienartifacts:welcome'
        return render(request, "alienartifacts/consentform.html", {
            "link_url": link_url,
        })
    except Exception as e:
        logger.error('Error in %s', 'consentformStandard', exc_info=e)


def consentformProlific(request):
    try:
        #Grab information from the URL parameters
        request.session['external_session_ID'] = request.GET.get("SESSION_ID")
        request.session['external_study_ID'] = request.GET.get("STUDY_ID")
        request.session['external_ID'] = request.GET.get("PROLIFIC_PID")
        #Tell it where to send users
        link_url = 'alienartifacts:welcome'
        return render(request, "alienartifacts/consentform.html", {
            "link_url": link_url,
        })
    except Exception as e:
        logger.error('Error in %s', 'consentformProlific', exc_info=e)


def welcome(request):
    logger.info('In welcome function')
    check_sustance_form = False
    try:
        # return render(request, "alienartifacts/welcome.html")
        if request.method == "POST":
            # Check the reCAPTCHA
            recaptcha_valid = True            
            if not DEBUG:
                ''' Begin reCAPTCHA validation '''
                recaptcha_response = request.POST.get('g-recaptcha-response')
                url = 'https://www.google.com/recaptcha/api/siteverify'
                values = {
                    'secret': os.environ['GOOGLE_RECAPTCHA_SECRET_KEY'],
                    'response': recaptcha_response
                }
                data = urllib.parse.urlencode(values).encode()
                req = urllib.request.Request(url, data=data)
                response = urllib.request.urlopen(req)
                result = json.loads(response.read().decode())                
                ''' End reCAPTCHA validation '''
                if not result['success']:
                    recaptcha_valid = False
            if recaptcha_valid:
                # Check if a new user needs to be created
                if (not 'external_ID' in request.session) or(('external_ID' in request.session) and\
                        (not Subject.objects.filter(external_ID=request.session['external_ID']).exists())):
                    # Go through and process the form for a new user
                    form = RegistrationForm(request.POST)
                    if form.is_valid():
                        #Create variables to be entered
                        if PROLIFIC:
                            if DEPLOYMENT:
                                subject_source = 'prolific'
                            else:
                                subject_source = 'internal'
                            user_ID = request.session['external_ID']
                            external_study_ID = request.session['external_study_ID']
                            external_session_ID = request.session['external_session_ID']
                        else:
                            user_ID = form.cleaned_data["user_ID"]
                            subject_source = form.cleaned_data["subject_source"]
                            external_study_ID = 'foo'
                            external_session_ID = 'bar'
                        age = form.cleaned_data["age"]
                        age_str = getAgeStr(age, age_list=AGES)
                        gender = form.cleaned_data["gender"]
                        sex = form.cleaned_data["sex"]
                        education = form.cleaned_data["education"]
                        start_time = form.cleaned_data["start_time"]
                        #Check if subject exists, if not create them
                        if Subject.objects.filter(external_ID=user_ID,external_source=subject_source).exists():
                            if DEPLOYMENT:
                                return alreadyCompleted(request)
                            subject = Subject.objects.filter(external_ID=user_ID)[0]
                        else:
                            subject = Subject(external_ID=user_ID, age=age_str, gender=gender, sex=sex, age_numeric=age,
                                              education=education,external_source=subject_source)
                            subject.save()
                    else:
                        raise ValueError('Invalid Form')
                else: # The user exists, and we have their info from the URL
                    user_ID = request.session['external_ID']
                    external_study_ID = request.session['external_study_ID']
                    external_session_ID = request.session['external_session_ID']
                    subject = Subject.objects.filter(external_ID=user_ID)[0]
                    start_time = datetime.now()
                    check_sustance_form = True
                #Create a new Session
                payment_token = getPaymentToken()
                end_time = datetime.now()  # Will update on each refresh
                # If they're just answering questionnaires
                if WEBAPP_USE == 'screen':
                    session = Session(start_time=start_time, end_time=end_time, payment_token=payment_token,
                                      subject=subject,external_session_ID=external_session_ID,
                                      external_study_ID=external_study_ID)
                    session.task = 'screen'
                # If they're doing the task as well
                elif (WEBAPP_USE == 'task') or (WEBAPP_USE == 'both'):
                    if TASK == 'example-generalization':
                        conditioning, generalization = checkSessionAtts(task=TASK,STIMULI_BLOCK_0=STIMULI_BLOCK_0,
                                                                        STIMULI_BLOCK_1=STIMULI_BLOCK_1)
                        reward_rules, valid_keys, conversion = assignKeys(REWARD_RULES, POSSIBLE_KEYS,\
                                                BLOCK_CATEGORIES, restrict_key_pattern=RESTRICT_KEY_PATTERN)
                        session = Session(start_time=start_time, end_time=end_time, payment_token=payment_token,
                                    subject=subject, conditioning_attributes=conditioning,key_conversion=conversion,
                                    external_study_ID=external_study_ID,external_session_ID=external_session_ID,
                                    generalization_attributes=generalization,
                                    confidence_key_conversion=CONVERSION_CONFIDENCE_KEYS)
                        #Organize Stimulus Information
                        stimulus_order_block_0 = getStimulusOrder(STIMULUS_COMBINATIONS_BLOCK_0, N_TRIALS_BLOCK_0,
                                                      trials_per_stim=TRIALS_PER_STIM_BLOCK_0, structured=STRUCTURED)
                        stimulus_order_block_1 = getStimulusOrder(STIMULUS_COMBINATIONS_BLOCK_1, N_TRIALS_BLOCK_1,
                                                      trials_per_stim=TRIALS_PER_STIM_BLOCK_1, structured=STRUCTURED)
                        stimulus_order_block_1 = [indx+len(STIMULUS_COMBINATIONS_BLOCK_0) for indx in
                                                  stimulus_order_block_1]
                        request.session['stimulus_order'] = stimulus_order_block_0 + stimulus_order_block_1
                        request.session['block'] = (np.append(np.zeros(N_TRIALS_BLOCK_0),
                                                              np.ones(N_TRIALS_BLOCK_1))).astype(int).tolist()
                        request.session['reward_rules'] = reward_rules
                        request.session['valid_keys'] = valid_keys
                    elif (TASK == 'context-generalization') or (TASK == 'context-generalization_v1') or \
                            (TASK == 'context-generalization_v2') or (TASK == 'diagnostic'):
                        set_1, set_2 = checkSessionAtts(task=TASK,STIMULI_BLOCK_0=STIMULI_BLOCK_0,
                                                                        STIMULI_BLOCK_1=STIMULI_BLOCK_1)
                        reward_rules, valid_keys, conversion = assignKeys(REWARD_RULES, POSSIBLE_KEYS,\
                                                        BLOCK_CATEGORIES, restrict_key_pattern=RESTRICT_KEY_PATTERN)
                        session = Session(start_time=start_time, end_time=end_time, payment_token=payment_token,
                                    subject=subject, set_1_attribute=set_1, set_2_attribute=set_2,
                                    external_study_ID=external_study_ID,external_session_ID=external_session_ID,
                                    key_conversion=conversion, confidence_key_conversion=CONVERSION_CONFIDENCE_KEYS)
                        stimulus_order_block_0 = getStimulusOrder(STIMULUS_COMBINATIONS_BLOCK_0, N_TRIALS_BLOCK_0,
                                                                  trials_per_stim=TRIALS_PER_STIM_BLOCK_0,
                                                                  structured=STRUCTURED)
                        stimulus_order_block_1 = getStimulusOrder(STIMULUS_COMBINATIONS_BLOCK_1, N_TRIALS_BLOCK_1,
                                                                  trials_per_stim=TRIALS_PER_STIM_BLOCK_1,
                                                                  structured=STRUCTURED)
                        stimulus_order_block_2 = getStimulusOrder(STIMULUS_COMBINATIONS_BLOCK_2, N_TRIALS_BLOCK_2,
                                                                  trials_per_stim=TRIALS_PER_STIM_BLOCK_2,
                                                                  structured=STRUCTURED)
                        request.session['stimulus_order'] = stimulus_order_block_0 + stimulus_order_block_1 + \
                                                            stimulus_order_block_2
                        request.session['block'] = (np.concatenate((np.zeros(N_TRIALS_BLOCK_0), \
                                                              np.ones(N_TRIALS_BLOCK_1), \
                                                              np.ones(N_TRIALS_BLOCK_2)*2))).astype(int).tolist()
                        request.session['reward_rules'] = reward_rules
                        request.session['valid_keys'] = valid_keys
                        if TASK == 'diagnostic':
                            request.session['diagnostic_block'] = 0
                    else:
                        raise ValueError(f'{TASK} is invalid for the TASK variable.')
                    session.task = TASK
                session.project = PROJECT_NAME
                session.save()
                # If we need to check for substances
                if check_sustance_form:
                    form_substance = substancesModelForm(request.POST, instance=session)
                    if form_substance.is_valid():
                        form_substance.save()
                    else:
                        raise ValueError('Problem with the checking substances in the welcome view')
                #Set variables for this visit to the site
                request.session['session_ID'] = session.id
                request.session['subject_ID'] = subject.id
                request.session['trial_number'] = 0
                request.method = 'GET'
                # Send them to the next page!
                if (WEBAPP_USE == 'screen') or (WEBAPP_USE == 'both'):
                    return questionnaires(request)
                elif WEBAPP_USE == 'task':
                    return instructions(request)
                else:
                    raise ValueError(f'{WEBAPP_USE} is invalid for WEBAPP_USE')
        if not DEBUG:                        
            recaptcha = {
                'bool': True,
                'src': 'https://www.google.com/recaptcha/api.js',
                'site_key': os.environ['GOOGLE_RECAPTCHA_SITE_KEY']
            }
        else:
            recaptcha = {
                'bool': False,
                'src': '',
                'site_key': ""
            }
        existing_subject = ('external_ID' in request.session) and \
                Subject.objects.filter(external_ID=request.session['external_ID']).exists()
        welcome_message = createWelcomeMessage(new_user=(existing_subject<1), webapp_use=WEBAPP_USE)
        if existing_subject:            
            form = makeSubstancesModelForm()
        else:            
            form = RegistrationForm(initial={'start_time': datetime.now()})
        return render(request, "alienartifacts/welcome.html", {
            "form": form,
            "recaptcha": recaptcha,
            'welcome_message': welcome_message
        })
    except Exception as e:
        logger.error('Error in %s', 'consentformProlific', exc_info=e)


def checkAttention(formset,form_att_check):
    # Check if they got the psych history one right
    if form_att_check.cleaned_data["attention_checkbox"] is not None:
        pass_attention_checkbox = ('pass_attention_check' in form_att_check.cleaned_data["attention_checkbox"]) and \
                                    ('fail_attention_check' not in form_att_check.cleaned_data["attention_checkbox"])
    else:
        pass_attention_checkbox = False
    # Check for the hidden questions
    correct_responses = 0
    bapq_question = None
    for question in formset.cleaned_data:
        if question['questionnaire_name'] == 'att_check':
            correct_responses += question['answer']
        if (question['questionnaire_name'] == 'bapq') and (question['subscale'] == 'Attention Check'):
            bapq_question = (question['answer'] == 5)
    if bapq_question is None:
        pass_hidden_questions = (correct_responses == 2)
    else:
        pass_hidden_questions = (correct_responses == 2) * bapq_question
    # Return if they got both right
    return pass_hidden_questions & pass_attention_checkbox


def attentionfailure(request):
    # They failed the attention test
    return render(request, "alienartifacts/attentionfailure.html", {
        "token": ATTENTION_FAILURE_TOKEN,
    })


def questionnaires(request):
    logger.info('In questionnaires function')
    if request.method == "POST":
        # Get sessions
        session = Session.objects.filter(id=request.session['session_ID'])[0]
        subject = Subject.objects.filter(sessions=session)[0]
        # Pull data
        form_substance = substancesModelForm(request.POST, instance=session)
        formset_f = modelformset_factory(QuestionnaireQ, exclude=('session',))
        formset = formset_f(request.POST)
        form_mh = mentalHealthModelForm(request.POST, instance=subject)
        form_att_check = attentionCheckList(request.POST)
        if all([form_substance.is_valid(),formset.is_valid(),form_mh.is_valid(),form_att_check.is_valid()]):
            form_substance.save()
            form_mh.save()
            questions = formset.save(commit=False)
            for question in questions:
                question.session = Session.objects.filter(id=request.session['session_ID'])[0]
                question.save()
            if ATTENTION_CHECK:
                pass_attention_check = checkAttention(formset,form_att_check)
            else:
                pass_attention_check = True
            if not pass_attention_check:
                session.passed_attention_check = False
                session.save()
                return attentionfailure(request)
            else:
                session = Session.objects.filter(id=request.session['session_ID'])[0]
                session.questionnaire_completed = True
                session.save()
                if WEBAPP_USE == 'screen':
                    session = Session.objects.filter(id=request.session['session_ID'])[0]
                    session.session_completed = True
                    session.save()
                    return token(request)
                elif (WEBAPP_USE == 'task') or (WEBAPP_USE == 'both'):
                    return instructions(request)
                else:
                    raise ValueError(f'{WEBAPP_USE} is invalid for WEBAPP_USE')
        else:
            raise ValueError('Problem with the questionnaire formset')
    else:
        session = Session.objects.filter(id=request.session['session_ID'])[0]
        subject = Subject.objects.filter(sessions=session)[0]
        form_substance = makeSubstancesModelForm(instance=session)
        form_mh = makeMentalHealthModelForm(instance=subject)
        formset = makeQuestionnaireFormSet(QUESTIONNAIRES)
        form_att_check = attentionCheckList()
        return render(request, "alienartifacts/questionnaires.html", {
            "formset": formset,
            'form_mh': form_mh,
            'form_substance': form_substance,
            'form_att_check': form_att_check
        })


def tutorial(request):
    stimuli = TutorialStimulus.objects.all()
    session = Session.objects.filter(id=request.session['session_ID'])[0]
    payment_token = session.payment_token
    stimulus_urls = []
    spaceship = []
    setting = []
    reward_probabilities = []
    valid_keys = []
    for s in range(len(stimuli)):
        stimulus_urls.append(stimuli[s].image.url)
        spaceship.append(stimuli[s].spaceship)
        setting.append(stimuli[s].setting)
        reward_probabilities.append(list(stimuli[s].reward_probabilities.values()))
        valid_keys.append(list(stimuli[s].reward_probabilities.keys()))
    instruction_stimuli = [
        ['green-spaceship', 'space'],
        ['red-spaceship', 'space'],
        ['blue-spaceship', 'tan-planet'],
        ['purple-spaceship', 'green-planet'],
        ['no-spaceship', 'gold-planet'],
        ['no-spaceship', 'blue-planet'],
        ['no-spaceship', 'gold-planet']
    ]
    reward_stim_urls = [RewardStimulus.objects.filter(outcome='reward',type='diamond').first().image.url,
                        RewardStimulus.objects.filter(outcome='noreward',type='diamond').first().image.url]
    if TASK == 'example-generalization':
        task_link = 'alienartifacts:onepageexamplegentask'
    elif (TASK == 'context-generalization') or (TASK == 'context-generalization_v1') or \
            (TASK == 'context-generalization_v2'):
        if CONFIDENCE_REPORT:
            task_link = 'alienartifacts:onepagecontextgenmetacogtask'
        else:
            task_link = 'alienartifacts:onepagecontextgentask'
    elif TASK == 'diagnostic':
        task_link = 'alienartifacts:onepagediagnostic'
    goodbye_link = 'alienartifacts:token'

    return render(request, "alienartifacts/tutorial.html", {
        'stimulus_urls': stimulus_urls,
        'reward_stim_urls': reward_stim_urls,
        'spaceship': spaceship,
        'setting': setting,
        'reward_probabilities': reward_probabilities,
        'valid_keys': valid_keys,
        'instruction_stimuli': instruction_stimuli,
        'payment_token': payment_token,
        'task_link': task_link,
        'goodbye_link': goodbye_link
    })


def tutorialmetacog(request):
    stimuli = TutorialStimulus.objects.all()
    session = Session.objects.filter(id=request.session['session_ID'])[0]
    payment_token = session.payment_token
    stimulus_urls = []
    spaceship = []
    setting = []
    reward_probabilities = []
    valid_keys = []
    for s in range(len(stimuli)):
        stimulus_urls.append(stimuli[s].image.url)
        spaceship.append(stimuli[s].spaceship)
        setting.append(stimuli[s].setting)
        reward_probabilities.append(list(stimuli[s].reward_probabilities.values()))
        valid_keys.append(list(stimuli[s].reward_probabilities.keys()))
    instruction_stimuli = [
        ['green-spaceship', 'space'],
        ['red-spaceship', 'space'],
        ['blue-spaceship', 'tan-planet'],
        ['purple-spaceship', 'green-planet'],
        ['no-spaceship', 'gold-planet'],
        ['no-spaceship', 'blue-planet'],
        ['no-spaceship', 'gold-planet']
    ]
    reward_stim_urls = [RewardStimulus.objects.filter(outcome='reward',type='diamond').first().image.url,
                        RewardStimulus.objects.filter(outcome='noreward',type='diamond').first().image.url]
    if TASK == 'example-generalization':
        task_link = 'alienartifacts:onepageexamplegentask'
    elif (TASK == 'context-generalization') or (TASK == 'context-generalization_v1') or \
            (TASK == 'context-generalization_v2'):
        if CONFIDENCE_REPORT:
            task_link = 'alienartifacts:onepagecontextgenmetacogtask'
        else:
            task_link = 'alienartifacts:onepagecontextgentask'
    elif TASK == 'diagnostic':
        task_link = 'alienartifacts:onepagediagnostic'
    goodbye_link = 'alienartifacts:token'

    return render(request, "alienartifacts/tutorialmetacog.html", {
        'stimulus_urls': stimulus_urls,
        'reward_stim_urls': reward_stim_urls,
        'spaceship': spaceship,
        'setting': setting,
        'reward_probabilities': reward_probabilities,
        'valid_keys_response': valid_keys,
        'valid_keys_confidence': VALID_CONFIDENCE_KEYS,
        'instruction_stimuli': instruction_stimuli,
        'payment_token': payment_token,
        'task_link': task_link,
        'goodbye_link': goodbye_link
    })


def alreadyCompleted(request):
    return render(request,"alienartifacts/alreadycompleted.html")


def instructions(request):
    logger.info('In instructions function')
    if DEPLOYMENT:
        if CONFIDENCE_REPORT:
            link_url = 'alienartifacts:tutorialmetacog'
        else:
            link_url = 'alienartifacts:tutorial'
    else:
        if TASK == 'example-generalization':
            link_url = 'alienartifacts:onepageexamplegentask'
        elif (TASK == 'context-generalization') or (TASK == 'context-generalization_v1') or \
                (TASK == 'context-generalization_v2'):
            if CONFIDENCE_REPORT:
                link_url = 'alienartifacts:onepagecontextgenmetacogtask'
            else:
                link_url = 'alienartifacts:onepagecontextgentask'
        elif TASK == 'diagnostic':
            link_url = 'alienartifacts:onepagediagnostic'
    #Provide the user instructions on how to perform the task
    return render(request, "alienartifacts/instructions.html", {
        'instructions': INSTRUCTIONS,
        'link_url': link_url
    })


def onePageExampleGenUpdate(request):
    print('In onepageupdate')
    if request.method == 'GET':
        # Get data from request
        start_times = json.loads(request.GET.get("start_times"))
        end_times = json.loads(request.GET.get("end_times"))
        responses = json.loads(request.GET.get("responses"))
        # Store data from request
        outcomes = np.array(request.session['outcomes'])
        # Add the data to the trial and the trial to the session
        session = Session.objects.filter(id=request.session['session_ID'])[0]
        for t in range(len(responses)):
            start_time = datetime.fromtimestamp(int(start_times[t]) / 1000.0)
            end_time = datetime.fromtimestamp(int(end_times[t]) / 1000.0)
            current_block = request.session['block'][request.session['trial_number']+t]
            reward = outcomes[t,request.session['valid_keys'][current_block].index(responses[t])]
            stimulus_key = getStimulusKey(request, request.session['trial_number']+t)
            stimulus = Stimulus.objects.filter(color=stimulus_key[0], shape=stimulus_key[1], texture=stimulus_key[2], \
                                               size=stimulus_key[3])[0]
            reward_prob_dict = getRewardProbabilities(color=stimulus_key[0], shape=stimulus_key[1],
                                                      texture=stimulus_key[2],size=stimulus_key[3],
                                                      reward_rules=request.session['reward_rules'])
            largest_chosen, _ = chooseLargest(responses[t], reward_prob_dict)
            trial = Trial(stimulus_id=stimulus.id, reward=reward, reward_probs_record=reward_prob_dict,
                          block=BLOCK_NAMES[current_block], start_time=start_time, end_time=end_time,
                          response=responses[t], stimulus=stimulus, session=session)
            trial.save()
            session.n_trials += 1
            session.total_reward += reward
            session.end_time = end_time
            if current_block > 0:
                session.conditioning_completed = True
            session.save()
        request.session['trial_number'] += len(responses)
        # If it's the last trial, send them to goodbye
        if request.session['trial_number'] >= (N_TRIALS_BLOCK_0 + N_TRIALS_BLOCK_1 -1):
            return JsonResponse({
                # "outcomes": outcomes,
                "stimuli": '[]',
                "obscured": '[]',
                "last": 1
            })
        # Otherwise, prepare for next block.
        if request.session['trial_number'] + SINGLE_PAGE_BLOCK_LENGTH >= N_TRIALS_BLOCK_0 + N_TRIALS_BLOCK_1:
            block_length = (N_TRIALS_BLOCK_0 + N_TRIALS_BLOCK_1) - request.session['trial_number']
        else:
            block_length = SINGLE_PAGE_BLOCK_LENGTH
        # Return info for the next block
        indx_block = np.arange(request.session['trial_number'],
                               (request.session['trial_number'] + block_length))
        block_reward_probs = np.array(request.session['reward_probabilities'])[
                             np.array(request.session['stimulus_order'])[indx_block], :]
        outcomes = (np.random.rand(block_reward_probs.shape[0],
                                   block_reward_probs.shape[1]) < block_reward_probs).astype(int)
        obscured = json.dumps(obscureOutcomes(outcomes))
        request.session['outcomes'] = outcomes.tolist()
        stimuli = np.array(request.session['stimulus_order'])[indx_block]
        stimuli = json.dumps(stimuli.tolist())
        return JsonResponse({
            "stimuli": stimuli,
            "obscured": obscured,
            "last": 0
        })


def onePageExampleGenTask(request):
    session = Session.objects.filter(id=request.session['session_ID'])[0]
    session.tutorial_completed = True
    session.save()
    current_block = request.session['block'][request.session['trial_number']]
    stimulus_urls, reward_probabilities = sessionStimulisRewardProbs(valid_keys=request.session['valid_keys'][current_block],
                                                                     reward_rules=request.session['reward_rules'],
                                                                     stimulus_combinations=STIMULUS_COMBINATIONS[0])
    block_reward_probs = reward_probabilities[request.session['stimulus_order'][:SINGLE_PAGE_BLOCK_LENGTH],:]
    outcomes = (np.random.rand(block_reward_probs.shape[0],block_reward_probs.shape[1]) < block_reward_probs).astype(int)
    obscured = obscureOutcomes(outcomes)
    request.session['outcomes'] = outcomes.tolist()
    request.session['reward_probabilities'] = reward_probabilities.tolist()
    stimuli = request.session['stimulus_order'][:SINGLE_PAGE_BLOCK_LENGTH]
    reward_stim_urls = [RewardStimulus.objects.filter(outcome='reward', type='diamond').first().image.url,
                        RewardStimulus.objects.filter(outcome='noreward', type='diamond').first().image.url]
    # Construct the instructions that appear above the stimulus
    response_text = 'Ways to activate:'
    for key, action in zip(request.session['valid_keys'][current_block],KEY_ACTIONS[current_block]):
        response_text += f' {action.lower()} (press "{key}"),'
    response_text = response_text[:-1] + '.'
    #Introduction at the beginning of session
    planet_intro = createPlanetIntros(valid_keys=request.session['valid_keys'][0], key_actions=KEY_ACTIONS[0],
                                      task='example-generalization')[0]
    return render(request, "alienartifacts/onepageexamplegentask.html", {
        "valid_keys": request.session['valid_keys'][current_block],
        "key_actions": KEY_ACTIONS,
        "stimulus_urls": stimulus_urls,
        "reward_stim_urls": reward_stim_urls,
        'response_text': response_text,
        # 'outcomes': outcomes,
        "stimuli": stimuli,
        'obscured': json.dumps(obscured),
        'planet_intro': planet_intro
    })


def onePageContextGenUpdate(request):
    print('In onepageupdate')
    if request.method == 'GET':
        # Get data from request
        start_times = json.loads(request.GET.get("start_times"))
        end_times = json.loads(request.GET.get("end_times"))
        responses = json.loads(request.GET.get("responses"))
        # Store data from request
        outcomes = np.array(request.session['outcomes'])
        # Add the data to the trial and the trial to the session
        session = Session.objects.filter(id=request.session['session_ID'])[0]
        initial_planet = request.session['block'][request.session['trial_number']]
        for t in range(len(responses)):
            start_time = datetime.fromtimestamp(int(start_times[t]) / 1000.0)
            end_time = datetime.fromtimestamp(int(end_times[t]) / 1000.0)
            current_planet = request.session['block'][request.session['trial_number']+t]
            reward = outcomes[t,request.session['valid_keys'][current_planet].index(responses[t])]
            stimulus_key = getStimulusKey(request, request.session['trial_number']+t)
            stimulus = Stimulus.objects.filter(color=stimulus_key[0], shape=stimulus_key[1], texture=stimulus_key[2], \
                                               size=stimulus_key[3])[0]
            reward_prob_dict = getRewardProbabilities(color=stimulus_key[0], shape=stimulus_key[1],
                                                      texture=stimulus_key[2],size=stimulus_key[3],
                                                      reward_rules=request.session['reward_rules'])
            largest_chosen, _ = chooseLargest(responses[t], reward_prob_dict)
            trial = Trial(stimulus_id=stimulus.id, reward=reward, reward_probs_record=reward_prob_dict,
                          block=BLOCK_NAMES[current_planet], start_time=start_time, end_time=end_time,
                          response=responses[t], stimulus=stimulus, session=session)
            trial.save()
            session.n_trials += 1
            session.total_reward += reward
            session.end_time = end_time
            if current_planet > 0: session.conditioning_completed = True
            session.save()
        request.session['trial_number'] += len(responses)
        try:
            next_planet = request.session['block'][request.session['trial_number']+1]
        except:
            next_planet = current_planet
        # If it's the last trial, send them to the next planet
        if request.session['trial_number'] >= (sum(N_TRIALS_PER_BLOCK) - 1) or initial_planet != next_planet:
            return JsonResponse({
                # "outcomes": outcomes,
                "stimuli": '[]',
                "obscured": '[]',
                "last": 1
            })
        # Otherwise, prepare for next set of trials.
        current_block = request.session['block'][request.session['trial_number']]
        if (request.session['trial_number'] + SINGLE_PAGE_BLOCK_LENGTH) > sum(N_TRIALS_PER_BLOCK[:current_block + 1]):
            block_length = sum(N_TRIALS_PER_BLOCK[:current_block + 1]) - request.session['trial_number']
        else:
            block_length = SINGLE_PAGE_BLOCK_LENGTH
        # Return info for the next set of trials
        indx_block = np.arange(request.session['trial_number'],
                               (request.session['trial_number'] + block_length))
        block_reward_probs = np.array(request.session['reward_probabilities'])[
                             np.array(request.session['stimulus_order'])[indx_block], :]
        outcomes = (np.random.rand(block_reward_probs.shape[0],
                                   block_reward_probs.shape[1]) < block_reward_probs).astype(int)
        obscured = json.dumps(obscureOutcomes(outcomes))
        request.session['outcomes'] = outcomes.tolist()
        stimuli = np.array(request.session['stimulus_order'])[indx_block]
        stimuli = json.dumps(stimuli.tolist())
        if (current_block == 2) and (not GENERALIZATION_FEEDBACK):
            print('here')
        return JsonResponse({
            "stimuli": stimuli,
            "obscured": obscured,
            "last": 0
        })


def onePageContextGenTask(request):
    try:
         # If this is the first, save the tutorial
        if request.session['trial_number'] == 0:        
            session = Session.objects.filter(id=request.session['session_ID'])[0]
            session.tutorial_completed = True
            session.save()
        # if the last, send them on their way!
        elif request.session['trial_number'] >= (sum(N_TRIALS_PER_BLOCK)-1):
            session = Session.objects.filter(id=request.session['session_ID'])[0]
            session.task_completed = True
            session.save()
            return goodbye(request)
        # Put together the stimuli and outcomes
        current_block = request.session['block'][request.session['trial_number']]
        trial_n = request.session['trial_number']        
        if (request.session['trial_number'] + SINGLE_PAGE_BLOCK_LENGTH) > sum(N_TRIALS_PER_BLOCK[:current_block+1]):            
            BLOCK_LENGTH = sum(N_TRIALS_PER_BLOCK[:current_block+1]) - request.session['trial_number']
        else:            
            BLOCK_LENGTH = SINGLE_PAGE_BLOCK_LENGTH
            
        
        stimulus_urls, reward_probabilities = sessionStimulisRewardProbs(valid_keys=request.session['valid_keys'][current_block],
                                                        stimulus_combinations=STIMULUS_COMBINATIONS[current_block],
                                                        reward_rules=request.session['reward_rules'])
        block_reward_probs = reward_probabilities[request.session['stimulus_order'][trial_n:(trial_n+BLOCK_LENGTH)],:]
        outcomes = (np.random.rand(block_reward_probs.shape[0],block_reward_probs.shape[1]) <= block_reward_probs).astype(int)
        obscured = obscureOutcomes(outcomes)
        request.session['outcomes'] = outcomes.tolist()
        request.session['reward_probabilities'] = reward_probabilities.tolist()
        stimuli = request.session['stimulus_order'][trial_n:(trial_n+BLOCK_LENGTH)]
        reward_stim_urls = [RewardStimulus.objects.filter(outcome='reward', type='diamond').first().image.url,
                            RewardStimulus.objects.filter(outcome='noreward', type='diamond').first().image.url]
        # Construct the instructions that appear above the stimulus
        response_text = 'Ways to activate:'
        
        
        for key, action in zip(request.session['valid_keys'][current_block],KEY_ACTIONS[current_block]):
            response_text += f' {action.lower()} (press "{key}"),'            
        
        
        response_text = response_text[:-1] + '.'
        planet_intros = createPlanetIntros(valid_keys=request.session['valid_keys'], key_actions=KEY_ACTIONS)
        
        #Determine if feedback will be provided
        
        if (current_block == 2) and (not GENERALIZATION_FEEDBACK):
        
            feedback_bool = False
        else:
        
            feedback_bool = True
        #Get rolling!xz
        return render(request, "alienartifacts/onepagecontextgentask.html", {
            "planet_intro": planet_intros[current_block],
            "valid_keys": request.session['valid_keys'][current_block],
            "response_text": response_text,
            "stimulus_urls": stimulus_urls,
            "reward_stim_urls": reward_stim_urls,
            # 'outcomes': outcomes,
            "stimuli": stimuli,
            'obscured': json.dumps(obscured),
            'feedback_bool': feedback_bool
        })
    except Exception as e:
        logger.error('Error at %s', 'onePageContextGenTask', exc_info=e)


def onePageDiagnosticUpdate(request):
    logger.info('In onePageDiagnosticUpdate')
    if request.method == 'GET':
        # Get data from request
        responses = json.loads(request.GET.get("responses"))
        diagnostic_counter = json.loads(request.GET.get("diagnostic_counter")) + 1
        # Store data from request
        # Add the data to the trial and the trial to the session
        request.session['trial_number'] += len(responses)
        if diagnostic_counter >= DIAGNOSTIC_COUNTER_BLOCK_LEN:
            return JsonResponse({
                # "outcomes": outcomes,
                "stimuli": '[]',
                "obscured": '[]',
                "diagnostic_counter": 0,
                "last": 1
            })
        # Otherwise, prepare for next set of trials.
        current_block = request.session['block'][request.session['trial_number']]
        if (request.session['trial_number'] + SINGLE_PAGE_BLOCK_LENGTH) > sum(N_TRIALS_PER_BLOCK[:current_block + 1]):
            block_length = sum(N_TRIALS_PER_BLOCK[:current_block + 1]) - request.session['trial_number']
        else:
            block_length = SINGLE_PAGE_BLOCK_LENGTH
        # Return info for the next set of trials
        indx_block = np.arange(request.session['trial_number'],
                               (request.session['trial_number'] + block_length))
        block_reward_probs = np.array(request.session['reward_probabilities'])[
                             np.array(request.session['stimulus_order'])[indx_block], :]
        outcomes = (np.random.rand(block_reward_probs.shape[0],
                                   block_reward_probs.shape[1]) < block_reward_probs).astype(int)
        obscured = json.dumps(obscureOutcomes(outcomes))
        request.session['outcomes'] = outcomes.tolist()
        stimuli = np.array(request.session['stimulus_order'])[indx_block]
        stimuli = json.dumps(stimuli.tolist())
        return JsonResponse({
            "stimuli": stimuli,
            "obscured": obscured,
            "diagnostic_counter": diagnostic_counter,
            "last": 0
        })


def onePageContextGenMetacogUpdate(request):
    print('In onepageupdate')
    # if request.method == 'GET':
    if request.method == 'POST':
        print('POST')
        # Get data from request
        print('data loading: start_times')
        start_times = json.loads(request.POST.get("start_times"))
        print('data loaded: start_times')
        print('data loading: end_times')
        end_times = json.loads(request.POST.get("end_times"))
        print('data loaded: end_times')
        print('data loading: responses')
        responses = json.loads(request.POST.get("responses"))
        print('data loaded: responses')
        print('data loading: confidence')
        confidence = json.loads(request.POST.get("confidence"))
        print('data loaded: confidence')
        # Store data from request
        print('data loading: outcomes')
        outcomes = np.array(request.session['outcomes'])
        print('data loaded: outcomes')
        # Add the data to the trial and the trial to the session
        session = Session.objects.filter(id=request.session['session_ID'])[0]
        initial_planet = request.session['block'][request.session['trial_number']]
        for t in range(len(responses)):
            print(f'Processing t {t}')
            start_time = datetime.fromtimestamp(int(start_times[t]) / 1000.0)
            end_time = datetime.fromtimestamp(int(end_times[t]) / 1000.0)
            current_planet = request.session['block'][request.session['trial_number'] + t]
            reward = outcomes[t, request.session['valid_keys'][current_planet].index(responses[t])]
            stimulus_key = getStimulusKey(request, request.session['trial_number'] + t)
            stimulus = Stimulus.objects.filter(color=stimulus_key[0], shape=stimulus_key[1], texture=stimulus_key[2], \
                                               size=stimulus_key[3])[0]
            reward_prob_dict = getRewardProbabilities(color=stimulus_key[0], shape=stimulus_key[1],
                                                      texture=stimulus_key[2], size=stimulus_key[3],
                                                      reward_rules=request.session['reward_rules'])
            largest_chosen, _ = chooseLargest(responses[t], reward_prob_dict)
            trial = Trial(stimulus_id=stimulus.id, reward=reward, reward_probs_record=reward_prob_dict,
                          block=BLOCK_NAMES[current_planet], start_time=start_time, end_time=end_time,
                          response=responses[t], stimulus=stimulus, session=session, confidence=confidence[t])
            trial.save()
            session.n_trials += 1
            session.total_reward += reward
            session.end_time = end_time
            if current_planet > 0: session.conditioning_completed = True
            session.save()
            print("Saving Session")
        request.session['trial_number'] += len(responses)
        try:
            next_planet = request.session['block'][request.session['trial_number'] + 1]
        except:
            next_planet = current_planet
        # If it's the last trial, send them to the next planet
        if request.session['trial_number'] >= (sum(N_TRIALS_PER_BLOCK) - 1) or initial_planet != next_planet:
            print("# If it's the last trial, send them to the next planet")
            return JsonResponse({
                # "outcomes": outcomes,
                "stimuli": '[]',
                "obscured": '[]',
                "last": 1
            })
        # Otherwise, prepare for next set of trials.
        print("# Otherwise, prepare for next set of trials.")
        current_block = request.session['block'][request.session['trial_number']]
        if (request.session['trial_number'] + SINGLE_PAGE_BLOCK_LENGTH) > sum(N_TRIALS_PER_BLOCK[:current_block + 1]):
            block_length = sum(N_TRIALS_PER_BLOCK[:current_block + 1]) - request.session['trial_number']
        else:
            block_length = SINGLE_PAGE_BLOCK_LENGTH
        # Return info for the next set of trials
        print("# Return info for the next set of trials")
        indx_block = np.arange(request.session['trial_number'],
                               (request.session['trial_number'] + block_length))
        block_reward_probs = np.array(request.session['reward_probabilities'])[
                             np.array(request.session['stimulus_order'])[indx_block], :]
        outcomes = (np.random.rand(block_reward_probs.shape[0],
                                   block_reward_probs.shape[1]) < block_reward_probs).astype(int)
        obscured = json.dumps(obscureOutcomes(outcomes))
        request.session['outcomes'] = outcomes.tolist()
        stimuli = np.array(request.session['stimulus_order'])[indx_block]
        stimuli = json.dumps(stimuli.tolist())
        if (current_block == 2) and (not GENERALIZATION_FEEDBACK):
            print('here')
        return JsonResponse({
            "stimuli": stimuli,
            "obscured": obscured,
            "last": 0
        })


def onePageContextGenMetacogTask(request):
    try:
        # If this is the first, save the tutorial
        if request.session['trial_number'] == 0:
            session = Session.objects.filter(id=request.session['session_ID'])[0]
            session.tutorial_completed = True
            session.save()
        # if the last, send them on their way!
        elif request.session['trial_number'] >= (sum(N_TRIALS_PER_BLOCK) - 1):
            session = Session.objects.filter(id=request.session['session_ID'])[0]
            session.task_completed = True
            session.save()
            return goodbye(request)
        # Put together the stimuli and outcomes
        current_block = request.session['block'][request.session['trial_number']]
        trial_n = request.session['trial_number']
        if (request.session['trial_number'] + SINGLE_PAGE_BLOCK_LENGTH) > sum(N_TRIALS_PER_BLOCK[:current_block + 1]):
            BLOCK_LENGTH = sum(N_TRIALS_PER_BLOCK[:current_block + 1]) - request.session['trial_number']
        else:
            BLOCK_LENGTH = SINGLE_PAGE_BLOCK_LENGTH

        stimulus_urls, reward_probabilities = sessionStimulisRewardProbs(
            valid_keys=request.session['valid_keys'][current_block],
            stimulus_combinations=STIMULUS_COMBINATIONS[current_block],
            reward_rules=request.session['reward_rules'])
        block_reward_probs = reward_probabilities[request.session['stimulus_order'][trial_n:(trial_n + BLOCK_LENGTH)],
                             :]
        outcomes = (np.random.rand(block_reward_probs.shape[0],
                                   block_reward_probs.shape[1]) <= block_reward_probs).astype(int)
        obscured = obscureOutcomes(outcomes)
        request.session['outcomes'] = outcomes.tolist()
        request.session['reward_probabilities'] = reward_probabilities.tolist()
        stimuli = request.session['stimulus_order'][trial_n:(trial_n + BLOCK_LENGTH)]
        reward_stim_urls = [RewardStimulus.objects.filter(outcome='reward', type='diamond').first().image.url,
                            RewardStimulus.objects.filter(outcome='noreward', type='diamond').first().image.url]
        # Construct the instructions that appear above the stimulus
        response_text = 'Ways to activate:'

        for key, action in zip(request.session['valid_keys'][current_block], KEY_ACTIONS[current_block]):
            response_text += f' {action.lower()} (press "{key}"),'

        response_text = response_text[:-1] + '.'
        planet_intros = createPlanetIntros(valid_keys=request.session['valid_keys'], key_actions=KEY_ACTIONS)

        # Determine if feedback will be provided

        if (current_block == 2) and (not GENERALIZATION_FEEDBACK):

            feedback_bool = False
        else:

            feedback_bool = True
        # Get rolling!xz
        return render(request, "alienartifacts/onepagecontextgenmetacogtask.html", {
            "planet_intro": planet_intros[current_block],
            "valid_keys_response": request.session['valid_keys'][current_block],
            "valid_keys_confidence": VALID_CONFIDENCE_KEYS,
            "response_text": response_text,
            "stimulus_urls": stimulus_urls,
            "reward_stim_urls": reward_stim_urls,
            # 'outcomes': outcomes,
            "stimuli": stimuli,
            'obscured': json.dumps(obscured),
            'feedback_bool': feedback_bool
        })
    except Exception as e:
        logger.error('Error at %s', 'onePageContextGenMetacogTask', exc_info=e)


def onePageDiagnostic(request):
    logger.info('In onePageDiagnostic')
    # If this is the first, save the tutorial
    if request.session['trial_number'] == 0:
        session = Session.objects.filter(id=request.session['session_ID'])[0]
        session.tutorial_completed = True
        session.save()
    # if the last, send them on their way!
    if request.session['diagnostic_block'] >= DIAGNOSTIC_COUNTER_N_BLOCKS:
        return goodbye(request)
    else:
        request.session['diagnostic_block'] += 1
    # Put together the stimuli and outcomes
    current_block = request.session['block'][request.session['trial_number']]
    trial_n = request.session['trial_number']
    if (request.session['trial_number'] + SINGLE_PAGE_BLOCK_LENGTH) > sum(N_TRIALS_PER_BLOCK[:current_block+1]):
        BLOCK_LENGTH = sum(N_TRIALS_PER_BLOCK[:current_block+1]) - request.session['trial_number']
    else:
        BLOCK_LENGTH = SINGLE_PAGE_BLOCK_LENGTH
    stimulus_urls, reward_probabilities = sessionStimulisRewardProbs(valid_keys=request.session['valid_keys'][current_block],
                                                    stimulus_combinations=STIMULUS_COMBINATIONS[current_block],
                                                    reward_rules=request.session['reward_rules'])
    block_reward_probs = reward_probabilities[request.session['stimulus_order'][trial_n:(trial_n+BLOCK_LENGTH)],:]
    outcomes = (np.random.rand(block_reward_probs.shape[0],block_reward_probs.shape[1]) <= block_reward_probs).astype(int)
    obscured = obscureOutcomes(outcomes)
    request.session['outcomes'] = outcomes.tolist()
    request.session['reward_probabilities'] = reward_probabilities.tolist()
    stimuli = request.session['stimulus_order'][trial_n:(trial_n+BLOCK_LENGTH)]
    reward_stim_urls = [RewardStimulus.objects.filter(outcome='reward', type='diamond').first().image.url,
                        RewardStimulus.objects.filter(outcome='noreward', type='diamond').first().image.url]
    # Construct the instructions that appear above the stimulus
    response_text = 'Ways to activate:'
    for key, action in zip(request.session['valid_keys'][current_block],KEY_ACTIONS[current_block]):
        response_text += f' {action} (press "{key}"),'
    response_text = response_text[:-1] + '.'
    diagnostic_counter = 0
    planet_intros = createPlanetIntros(valid_keys=request.session['valid_keys'],key_actions=KEY_ACTIONS)
    #Get rolling!
    return render(request, "alienartifacts/diagnostic.html", {
        "planet_intro": planet_intros[current_block],
        "valid_keys": request.session['valid_keys'][current_block],
        "response_text": response_text,
        "stimulus_urls": stimulus_urls,
        "reward_stim_urls": reward_stim_urls,
        # 'outcomes': outcomes,
        "stimuli": stimuli,
        'obscured': json.dumps(obscured),
        'block_number': request.session['diagnostic_block'],
        'diagnostic_counter': diagnostic_counter
    })


def fishy(request):
    return render(request, "alienartifacts/fishy.html")


def feedback(request,response):
    return render(request, "alienartifacts/feedback.html", {
        'response': response
    })


def token(request):
    session = Session.objects.filter(id=request.session['session_ID'])[0]
    payment_token = session.payment_token
    if (WEBAPP_USE == 'task') and (session.tutorial_completed is False):
        session.tutorial_completed = True
        session.task_completed = False
        session.session_completed = False
        session.end_time = datetime.now()  # Will update on each refresh
        session.save()
        token_message = f"Unfortunately, looks like you're having trouble learning the task. Space just isn't for you. " +\
                       "Even so, we'll give you a reward for trying. Back where you came from, enter the payment " +\
                        f"token:<br><br>{PAYMENT_TOKEN}"
        return render(request, "alienartifacts/token.html", {
            # 'payment_token': payment_token,
            'token_message': token_message
        })
    if WEBAPP_USE == 'screen':
        token_message = f'Thanks for taking the time to answer the questions! We will analyze your responses and ' + \
            f'determine if you are eligible for future studies. Your payment token for the task is:<br><br>' +\
            f'{payment_token}<br><br>To register for payment, please enter that token in the Prolific page. ' +\
            'You can close this window.'
    elif (WEBAPP_USE == 'task') or (WEBAPP_USE == 'both'):
        token_message = f'Your payment code for the task is:<br><br>{payment_token}<br><br>To register for ' + \
            'payment, please enter that in the Prolific page. You can close this window.'
    else:
        raise ValueError(f'{WEBAPP_USE} is invalid for WEBAPP_USE')

    if session.session_completed:
        return render(request, "alienartifacts/token.html", {
            # 'payment_token': payment_token,
            'token_message': token_message
        })

    else:
        return fishy(request)


def goodbye(request):
    session = Session.objects.filter(id=request.session['session_ID'])[0]
    if (TASK == 'example_generalization') and ((WEBAPP_USE == 'task') or (WEBAPP_USE == 'both')): # Hack due to how page was initially structured
        session = Session.objects.filter(id=request.session['session_ID'])[0]
        session.task_completed = True
        session.save()
    if request.method == "POST":
        form_free = strategyForm(request.POST)
        form_radio = strategyRadioForm(request.POST)
        form_difficulty = difficultyForm(request.POST)
        if form_difficulty.is_valid():
            session.perceived_difficulty = form_difficulty.cleaned_data["perceived_difficulty"]
            session.save()
            message = "Please briefly describe your strategy (or lack there of) for activating the artifacts."
            strategy = strategyForm()
            return render(request, "alienartifacts/goodbye.html", {
                'message': message,
                'form': strategy
            })
        elif form_free.is_valid():
            session.strategy = form_free.cleaned_data["strategy_free"]
            session.save()
            exit_message = "Please choose the option below that best captures what you wrote. There's no wrong answer!"
            strategy = strategyRadioForm()
            return render(request, "alienartifacts/goodbye.html", {
                'message': exit_message,
                'form': strategy
            })
        elif form_radio.is_valid():
            session.strategy_radio = form_radio.cleaned_data["strategy"]
            session.save()
            return token(request)

    # Update the session variable values
    session = Session.objects.filter(id=request.session['session_ID'])[0]
    chose_largest, _ = calcSessionPerformance(session)
    session.final_performance = np.mean(chose_largest)
    session.session_completed = True
    session.save()
    # Send them off with some gold
    total_reward = session.total_reward
    exit_message = EXIT_TEXT % (total_reward) + ' How difficult did you find the task?'
    perceived_difficulty = difficultyForm()
    return render(request, "alienartifacts/goodbye.html", {
        'message': exit_message,
        'form': perceived_difficulty
    })

