from aiogram.fsm.state import State, StatesGroup


class LanguageSelect(StatesGroup):
    waiting_language = State()


class PaymentFlow(StatesGroup):
    selecting_plan = State()
    selecting_period = State()
    awaiting_email = State()
    awaiting_payment = State()


class PromoFlow(StatesGroup):
    waiting_code = State()


class AdminFlow(StatesGroup):
    main_menu = State()
    broadcast_message = State()
    broadcast_confirm = State()
    user_lookup = State()
    add_balance = State()
    selecting_model = State()
