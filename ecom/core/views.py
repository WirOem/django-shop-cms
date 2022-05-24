from ast import Try
import imp
from locale import currency
from logging import exception
from pyexpat.errors import messages
from time import timezone
from unittest import result
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from core.forms import ProductForm
from django.contrib import messages
from core.models import *
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.csrf import csrf_exempt
from core.forms import CheckoutForm
import razorpay

razorpay_client=razorpay.Client(auth=(settings.RAZORPAY_ID,settings.RAZORPAY_SECRET))

# Create your views here.
def index(request):
    products=Product.objects.all()
    return render(request,'core/index.html',{'products':products})

def orderlist(request):
    if Order.objects.filter(user=request.user,ordered=False).exists():
        order=Order.objects.get(user=request.user,ordered=False)
        return render(request,'core/orderlist.html',{'order':order})
    return render(request,'core/orderlist.html',{'message':"Your Cart is Empty"})

def add_product(request):
    if request.method=='POST':
        form=ProductForm(request.POST,request.FILES)
        if form.is_valid():
            print('True')
            form.save()
            print('Data saved succesfully')
            messages.success(request, "Product added succesfully")
            return redirect('/')
        else:
            print('Not Working')
            messages.info(request, "Product is not added, Try again")
    else:
        form=ProductForm()
    return render(request,'core/add_product.html',{'form':form})

def product_desc(request,pk):
    product=Product.objects.get(pk=pk)
    return render(request,'core/product_desc.html',{'product':product})

def add_to_cart(request,pk):
    product=Product.objects.get(pk=pk)
    order_item, created=OrderItem.objects.get_or_create(
        product=product,
        user=request.user,
        ordered=False,
    )

    order_qs=Order.objects.filter(user=request.user,ordered=False)
    if order_qs.exists():
        order=order_qs[0]
        if order.items.filter(product__pk=pk).exists():
            order_item.quantity +=1
            order_item.save()
            messages.info(request,"Added Quantity Item")
            return redirect("product_desc",pk=pk)
        else:
            order.items.add(order_item)
            messages.info(request,"Item added to Cart")
            return redirect("product_desc",pk=pk)
    else:
        ordered_date=timezone.now()
        order=Order.objects.create(user=request.user,ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request,"Item added to Cart")
        return redirect("product_desc",pk=pk)

def add_item(request,pk):
    product=Product.objects.get(pk=pk)
    order_item, created=OrderItem.objects.get_or_create(
        product=product,
        user=request.user,
        ordered=False,
    )

    order_qs=Order.objects.filter(user=request.user,ordered=False)
    if order_qs.exists():
        order=order_qs[0]
        if order.items.filter(product__pk=pk).exists():
            if order_item.quantity<product.product_available_count:
                order_item.quantity +=1
                order_item.save() 
                messages.info(request,"Added Quantity Item")
                return redirect("orderlist")
            else:
                messages.info(request, "Sorry! Product is out of stock")
                return redirect("orderlist")
        else:
            order.items.add(order_item)
            messages.info(request,"Item added to Cart")
            return redirect("product_desc",pk=pk)
    else:
        ordered_date=timezone.now()
        order=Order.objects.create(user=request.user,ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request,"Item added to Cart")
        return redirect("product_desc",pk=pk)

def remove_item(request,pk):
    item=get_object_or_404(Product,pk=pk)
    order_qs=Order.objects.filter(
        user=request.user,
        ordered=False,
    )
    if order_qs.exists():
        order=order_qs[0]
        if order.items.filter(product__pk=pk).exists():
            order_item=OrderItem.objects.filter(
                product=item,
                user=request.user,
                ordered=False,
            )[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order_item.delete()
            messages.info(request, "Item quantity was updated")
            return redirect("orderlist")
        else:
            messages.info(request, "This item is not in your Cart")
            return redirect("orderlist")
    else:
        messages.info(request, "You do not have any Order")
        return redirect("orderlist")

def checkout_page(request):
    if CheckoutAddress.objects.filter(user=request.user).exists():
        return render(request,'core/checkout_address.html',{'payment_allow':"allow"})
    if request.method=='POST':
        form=CheckoutForm(request.POST)
        try:
            if form.is_valid():
                street_address=form.cleaned_data.get('street_address')
                apartment_address=form.cleaned_data.get('apartment_address')
                country=form.cleaned_data.get('country')
                zip_code=form.cleaned_data.get('zip_code')

                checkout_address=CheckoutAddress(
                    user=request.user,
                    street_address=street_address,
                    apartment_address=apartment_address,
                    country=country,
                    zip_code=zip_code,
                )
                checkout_address.save()
                print("It should render the summary page")
                return render(request,'core/checkout_address.html',{'payment_allow':"allow"})
        except ObjectDoesNotExist:
            messages.warning(request,'Failed Checkout')
            return redirect('checkout_page')
    
    else:
        form=CheckoutForm()
        return render(request,'core/checkout_address.html',{'form':form})

def payment(request):
    try:
        order=Order.objects.get(user=request.user, ordered=False)
        address=CheckoutAddress.objects.get(user=request.user)
        order_amount=order.get_total_price()
        order_currency="INR"
        order_receipt=order.order_id
        notes={
            "street_address":address.street_address,
            "apartment_address":address.apartment_address,
            "country":address.country,
            "zip":address.zip_code,
        }
        razorpay_order=razorpay_client.order.create(
            dict(
                amount=order_amount*100,
                currency=order_currency,
                receipt=order_receipt,
                notes=notes,
                payment_capture="0",
            )
        )
        print(razorpay_order["id"])
        order.razorpay_order_id=razorpay_order["id"]
        order.save()
        print("It should render the summary page")
        return render(
            request,
            "core/paymentsummaryrazorpay.html",
            {
                "order":order,
                "order_id":razorpay_order["id"],
                "orderId":order.order_id,
                "final_price":order_amount,
                "razorpay_merchant_id":settings.RAZORPAY_ID,
            },
        )
    except Order.DoesNotExist:
        print("Order not found")
        return HttpResponse("404 Error")

@csrf_exempt
def handlerequest(request):
    if request.method == "POST":
        try:
            payment_id=request.POST.get("razor_payment_id","")
            order_id=request.POST.get("razor_order_id","")
            signature=request.POST.get("razor_signature","")
            print(payment_id,order_id,signature)
            params_dict={
                "razorpay_order_id":order_id,
                "razorpay_payment_id":payment_id,
                "razorpay_signature":signature,
            }
            try:
                order_db=Order.objects.get(razorpay_order_id=order_id)
                print("Order found")
            except:
                print("Order not found")
                return HttpResponse("505 not found")
            order_db.razorpay_payment_id=payment_id
            order_db.razorpay_signature=signature
            order_db.save()
            print("Working.....")
            result=razorpay_client.utility.verify_payment_signature(params_dict)
            if result==None:
                print("Working Final Fine...")
                amount=order_db.get_total_price()
                amount=amount*100
                payment_status=razorpay_client.payment.capture(payment_id,amount)
                if payment_status is not None:
                    print(payment_status)
                    order_db.ordered=True
                    order_db.save()
                    print("Payment Success")
                    request.session[
                        "order_complete"
                        ]="Your order is succesfully placed"
                    return render(request,"core/invoice.html")
                else:
                    print("Payment Failed")
                    order_db.ordered=False
                    order_db.save()
                    request.session[
                        "order_failed"
                ]="Unfortunately your order could not be placed,try again!"
                return redirect("/")
            else:
                order_db.ordered=False
                order_db.save()
                return render(request,"core/paymentfailed.html")
        except:
            return HttpResponse("Error occured")



    

