# Register this blueprint by adding the following line of code 
# to your entry point file.  
# app.register_functions(crawler) 
# 
# Please refer to https://aka.ms/azure-functions-python-blueprints

import azure.functions as func
import logging

crawler = func.Blueprint()


@crawler.timer_trigger(schedule="* * * * * *", arg_name="myTimer", run_on_startup=True,
              use_monitor=False) 
def timer_trigger(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function executed.')