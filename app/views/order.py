__author__ = 'feliciaan'
from flask import url_for, render_template, abort, redirect, Blueprint, flash, session
from flask.ext.login import current_user, login_required
import random
from datetime import datetime

from app import app, db
from models import Order, OrderItem
from forms import OrderItemForm, OrderForm, AnonOrderItemForm

order_bp = Blueprint('order_bp', 'order')

@order_bp.route('/')
def orders(form=None):
    if form is None and not current_user.is_anonymous():
        form = OrderForm()
        form.populate()
    return render_template('orders.html', orders=get_orders(), form=form)


@order_bp.route('/create', methods=['POST'])
@login_required
def order_create():
    orderForm = OrderForm()
    orderForm.populate()
    if orderForm.validate_on_submit():
        order = Order()
        orderForm.populate_obj(order)
        db.session.add(order)
        db.session.commit()
        return redirect(url_for('.order', id=order.id))
    return orders(form=orderForm)


@order_bp.route('/<id>')
def order(id, form=None):
    order = Order.query.filter(Order.id == id).first()
    if order is None:
        abort(404)
    if current_user.is_anonymous() and not order.public:
        flash('Please login to see this order.', 'info')
        abort(401)
    if form is None:
        form = AnonOrderItemForm() if current_user.is_anonymous() else OrderItemForm()
        form.populate(order.location)
    if order.stoptime and order.stoptime < datetime.now():
        form = None
    total_price = sum([o.product.price for o in order.items])
    return render_template('order.html', order=order, form=form, total_price=total_price)


@order_bp.route('/<id>/create', methods=['POST'])
def order_item_create(id):
    current_order = Order.query.filter(Order.id == id).first()
    if current_order is None:
        abort(404)
    if current_order.stoptime and current_order.stoptime < datetime.now():
        abort(404)
    if current_user.is_anonymous() and not current_order.public:
        flash('Please login to see this order.', 'info')
        abort(401)
    form = AnonOrderItemForm() if current_user.is_anonymous() else OrderItemForm()
    form.populate(current_order.location)
    if form.validate_on_submit():
        item = OrderItem()
        form.populate_obj(item)
        item.order_id = id
        if not current_user.is_anonymous():
            item.user_id = current_user.id
        else:
            session['anon_name'] = item.name
        db.session.add(item)
        db.session.commit()
        flash('Ordered %s' % (item.product.name), 'success')
        return redirect(url_for('.order', id=id))
    return order(id, form=form)

@order_bp.route('/<order_id>/<item_id>/delete')
def delete_item(order_id, item_id):
    item = OrderItem.query.filter(OrderItem.id == item_id).first()
    id = None
    if not current_user.is_anonymous():
        id = current_user.id
    if item.can_delete(order_id, id, session.get('anon_name', '')):
        product_name = item.product.name
        db.session.delete(item)
        db.session.commit()
        flash('Deleted %s' % product_name, 'info')
        return redirect(url_for('.order', id=order_id))
    abort(404)


@order_bp.route('/<id>/volunteer')
@login_required
def volunteer(id):
    order = Order.query.filter(Order.id == id).first()
    if order is None:
        abort(404)
    if order.courrier_id is None or order.courrier_id == 0:
        order.courrier_id = current_user.id
        db.session.commit()
        flash("Thank you for volunteering!")
    else:
        flash("Volunteering not possible!")
    return redirect(url_for('.order', id=id))


@order_bp.route('/<id>/close')
@login_required
def close_order(id):
    order = Order.query.filter(Order.id == id).first()
    if order is None:
        abort(404)
    if (current_user.id == order.courrier_id or current_user.is_admin()) \
            and order.stoptime is None or (order.stoptime > datetime.now()):
        order.stoptime = datetime.now()
        if order.courrier_id == 0 or order.courrier_id is None:
            courrier = select_user(order.items)
            print(courrier)
            if courrier is not None:
                order.courrier_id = courrier.id
        db.session.commit()
        return redirect(url_for('.order', id=id))

app.register_blueprint(order_bp, url_prefix='/order')


def select_user(items):
    user = None
    # remove non users
    items = [i for i in items if i.user_id]

    if len(items) <= 0:
        return None

    while user is None:
        item = random.choice(items)
        user = item.user
        if user:
            if random.randint(user.bias, 100) < 80:
                user = None

    return user


def get_orders(expression=None):
    orders = []
    if expression is None:
        expression = ((datetime.now() > Order.starttime) & (Order.stoptime > datetime.now()) | (Order.stoptime == None))
    if not current_user.is_anonymous():
        orders = Order.query.filter(expression).all()
    else:
        orders = Order.query.filter((expression & (Order.public == True))).all()
    return orders
