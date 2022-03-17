from telegram.ext import PicklePersistence

print("Converting file 'text2cw_bot.data.new'")

pp = PicklePersistence(filename='text2cw_bot.data.new')

for k in pp.get_user_data():
    try:
        if isinstance(pp.user_data[k]['wpm'], int):
            pp.user_data[k]['wpm'] = [ pp.user_data[k]['wpm'] ]
            print(pp.user_data[k]['wpm'])
    except KeyError:
        pass
        
pp.flush()
