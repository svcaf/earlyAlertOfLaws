from collections import namedtuple
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import datetime
import traceback
import logging

from .parsing_options import site_addr
from models import Bill
from init_app import app


status_client_url = 'http://leginfo.legislature.ca.gov/faces/billStatusClient.xhtml'
updated_bill_info = namedtuple('updated_bill_info', ['id', 'last_action_name'])


LOGGING_LEVEL = logging.DEBUG
LOG_FILE_NAME = "notifications.log"

logger = logging.getLogger("notifications")
logger.setLevel(LOGGING_LEVEL)
handler = logging.FileHandler(LOG_FILE_NAME, 'a', 'utf-8')
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.info("Logger inited")
print("Logger inited")


def get_auth_smtp_server(server, port, login, passw):
    smtp = smtplib.SMTP(server, port)
    smtp.starttls()
    smtp.login(login, passw)
    return smtp

def save_ids_of_changed_bills(added, updated):
    # added on 1st line, updated on 2nd
    # comma separated leginfo ids
    # needed for email notifications
    logger.info("Saving ids of changed bills")
    with open("changed_bills.txt", "r") as f:
        lines = f.read().splitlines()
        if len(lines) == 0:
            lines = ["", ""]
        elif len(lines) == 1:
            lines = [lines[0], ""]
        elif len(lines) > 2:
            return
        line_1 = lines[0] + "|" if lines[0] else ""
        added_all = line_1 + "|".join(added) + "\n"
        updated = [";".join([bill_info.id, bill_info.last_action_name]) for bill_info in updated]
        line_2 = lines[1] + "|" if lines[1] else ""
        updated_all = line_2 + "|".join(updated)
    logger.info("Added bills ids: " + added_all)
    logger.info("Updated bills ids: " + updated_all)
    with open("changed_bills.txt", "w") as f:
        f.write(added_all)
        f.write(updated_all)

def clear_bills_changes():
    # clear changed_bills.txt file
    logger.info("Clearing bills changes")
    f = open("changed_bills.txt", "w")
    f.close()

def send_email_notifications(email_server, email_port, email_pass, sender_email):
    logger.info("Entering function send_email_notifications")
    print("Entering function send_email_notifications")
    from search import make_query
    authed_email_server = get_auth_smtp_server(email_server, email_port, sender_email, email_pass)
    with open("subscribed_emails.txt", "r") as f:
        email_lines = [line for line in f.read().splitlines() if line]
    with open("changed_bills.txt", "r") as f:
        lines = f.read().splitlines()
        if len(lines) == 0 or len(lines) > 2:
            return
        added = [bill for bill in lines[0].split("|") if bill]
        updated = dict()
        if len(lines) == 2:
            for bill_info in lines[1].split("|"):
                if not bill_info:
                    continue
                bill_info = bill_info.split(";")
                print(bill_info)
                bill_id = bill_info[0]
                try:
                    bill_last_action_name_prev = bill_info[1]
                except Exception as e:
                    print(e)
                    
                bill_info_tuple = updated_bill_info(id=bill_id,
                                                    last_action_name=\
                                                    bill_last_action_name_prev)
                updated[bill_id] = bill_info_tuple
    logger.info("Updated bills: " + str(updated))
    logger.info("Added bills: " + str(added))
    
    print("Added bills: " + str(added))
    print("Updated bills: " + str(updated))
    
    with app.app_context():
        for email_line in email_lines:
            receiver_email, kws, time_limit = email_line.split(":")
            kws = [kw.strip() for kw in kws.split(",")]
            changes = dict()
            for kw in kws:
                try:
                    kw_result_ids, total = make_query("bill", [kw], page=1, 
                                                      per_page=3000, time_limit=time_limit,
                                                      returned_val="leginfo_id")
                except:
                    logger.error(traceback.format_exc())
                    continue
                    
                #print(kw_result_ids[:100])
                #kw_result_ids, total = make_query("bill", [kw], page=1, 
                #                                  per_page=70, time_limit="1M")
                added_bills_for_kw = [kw for kw in added if kw in kw_result_ids]
                updated_bills_of_kw = [updated[id_] for id_ in updated.keys() if id_ in kw_result_ids]
                changes[kw] = [added_bills_for_kw, updated_bills_of_kw]
                #print("kw_result_ids", kw_result_ids)
                #print("updated_kw", updated_bills_of_kw)
            logger.info("Bills changes: " + str(changes))
            print("Bills changes: " + str(changes))
            send_changes(authed_email_server, sender_email, receiver_email, changes)
    authed_email_server.close()

def is_info_to_notify(changes):
    # changes is dict like
    # {'chinese': [[], []], 'education': [[], []]}
    #
    # check whether all values are empty (like in example above)
    return any([bool(v) for val in list(changes.values()) for v in val])

def get_msg_text(changes, email):
    logger.info("Getting message text")
    unsubscribe_link = site_addr + "unsubs/" + email
    kws_msgs = []
    is_info = is_info_to_notify(changes)
    if not is_info:
        return
    with app.app_context():
        for kw, items in changes.items():
            added, updated = items
            if not added and not updated:
                continue
            added_msgs = ["Added bills:"]
            for id_ in added:
                bill = Bill.find_by_leginfo_id(id_)
                bill_subject = bill.subject
                bill_link = status_client_url + '?bill_id=' + id_
                bill = Bill.find_by_leginfo_id(id_)
                bill_code = bill.code
                added_msgs.append(bill_code + " (" + bill_subject + "). Link: " + bill_link)
            updated_msgs = ["Updated bills:"]
            for bill_info in updated:
                bill_id = bill_info.id
                prev_last_action_name = bill_info.last_action_name
                bill = Bill.find_by_leginfo_id(bill_id)
                bill_subject = bill.subject
                last_action_name = bill.last_action_name
                bill_code = bill.code
                bill_link = status_client_url + '?' + bill_id
                if last_action_name:
                    la_change = prev_last_action_name + " - " + last_action_name
                else:
                    la_change = prev_last_action_name
                updated_msgs.append(bill_code + " (" + bill_subject + "). Last action change: " + la_change
                                   + ". Link: " + bill_link)
            if len(added_msgs) > 1:
                added_msg = "\n    ".join(added_msgs)
            else:
                added_msg = ""
            
            if len(updated_msgs) > 1:
                updated_msg = "\n    ".join(updated_msgs)
            else:
                updated_msg = ""
                
            kw_msg = f"""
{kw}

"""
            if added_msg:
                kw_msg += added_msg + "\n"
            if updated_msg:
                kw_msg += updated_msg + "\n"
            if added_msg or updated_msg:
                kws_msgs.append(kw_msg)
        kws_msgs = "\n".join(kws_msgs)
        text = \
        f"""
Here are updates for every keyword you subsribed on California Bills Monitoring App.

{kws_msgs} 
You can unsubscribe using following link: {unsubscribe_link}
"""
        logger.info("Email text: \n" + text)
        return text

def send_email(server, from_, to, subject, msg_text=None, html_msg_text=None, type_="plain"):
    msg = MIMEMultipart()
    msg.add_header('From', from_)
    msg.add_header("To", to)
    msg.add_header("Subject", subject)
    if type_=="plain":
        msg.attach(MIMEText(msg_text, "plain"))
    if type_=="html" and html_msg_text:
        msg.attach(MIMEText(html_msg_text, "html"))    
    server.sendmail(
      from_,
      to,
      msg.as_string().encode("utf-8"))

def send_changes(server, from_, to, changes):
    logger.info("Sending email notifications")
    msg_text = get_msg_text(changes, to)
    if not msg_text:
        logger.info("No info to notify")
        print("No info to notify")
        return
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    subj = f'California Bills Updates for ' + now
    try:
        send_email(server, from_, to, subj, msg_text)
    except Exception:
        logger.error(traceback.format_exc())
        print(traceback.format_exc())
        return traceback.format_exc()
    
def send_email_subs_start_notification(receiver_email, kws, time_limit, email_server, 
                                       email_acc, email_port, email_pass):
    authed_email_server = get_auth_smtp_server(email_server, email_port, email_acc, email_pass)
    subject = "You have subscribed to email alerts on California Bills Monitoring App"
    kws = "Specified keywords: " + ", ".join(kws)
    time_limit = "Time limit: " + str(time_limit)
    unsubscribe_link = site_addr + "unsubs/" + receiver_email
    
    msg_text = "Subscription to email alerts on California Bills Monitoring App successful\n"
    msg_text += kws + '\n'
    msg_text += f'You can unsubscribe using following link: {unsubscribe_link}'
    

    html_msg_text = f"""
<html>
  <head></head>
  <body>
    <h2>Subscription to email alerts on California Bills Monitoring App successful</h2>
    <p>Every Sunday you will get info about new and updated bills that contain any of keywords you specified.<p>
    <p>{kws}</p>
    <p> Time limit is max publishing date for bill. If bill's publishing date is longer ago from now than specified in Time limit field, then you won't receive updates on that bill (if you prefer to not to get updates about too old bills).</p>
    <p>{time_limit}</p>
    <p>You can unsubscribe using following link: <a href="{unsubscribe_link}">{unsubscribe_link}</a></p>
  </body>
</html>

""".replace("http", "https")
    send_email(authed_email_server, email_acc, receiver_email, subject, html_msg_text=html_msg_text, type_="html")

