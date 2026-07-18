from django.http import JsonResponse
from ninja import Router
from workbook.schemas import WorkbookCreateSchema, TransactionCreateSchema, TransactionUpdateSchema, \
    WorkbookUpdateSchema
from workbook.models import Workbook, Transaction
from workbook.serializer import WorkbookSerializer, TransactionSerializer
from django.shortcuts import get_object_or_404
from ninja.security import django_auth



router = Router()

@router.get("/list", auth=django_auth)
def get_user_workbook(request):
    print(request.user)
    if request.user.is_authenticated:
        user_workbooks = Workbook.objects.filter(user=request.user)
        if user_workbooks:
            serializer = WorkbookSerializer(user_workbooks, many=True)
            return JsonResponse({
                "status": "success",
                "user_workbooks": serializer.data
            }, status=200)
        else:
            return JsonResponse({"status": "records not found"}, status=200)
    return JsonResponse({
        "status": "fail",
        "message": "You are not authenticated"
    }, status=401)

@router.get("/all_workbooks")
def get_all_workbooks(request):
    workbooks = Workbook.objects.all()
    serializer = WorkbookSerializer(workbooks, many=True)
    return JsonResponse({"status": "success", "workbooks": serializer.data}, status=200)


@router.get("/detail/{workbook_id}", auth=django_auth)
def get_workbook_transactions(request, workbook_id:int):
    if not request.user.is_authenticated:
        return JsonResponse({
            "status": "fail",
        }, status=401)
    transaction = Transaction.objects.filter(workbook_id=workbook_id)
    if not transaction:
        return JsonResponse({"status": "records not found"}, status=200)
    serializer = TransactionSerializer(transaction, many=True)
    return JsonResponse({"status": "success", "transactions": serializer.data}, status=200)


# --- CREATE WORKBOOK ---
@router.post("create")
def create_workbook(request, payload: WorkbookCreateSchema):
    if not request.user.is_authenticated:
        return JsonResponse({"status": "fail", "message": "Unauthorized"}, status=401)

    # Create the workbook linked to the logged-in user
    workbook = Workbook.objects.create(
        user=request.user,
        title=payload.title,
        opening_balance=payload.opening_balance,
    )
    return JsonResponse({
        "status": "success",
        "message": "Workbook created",
        "id": workbook.id
    }, status=201)

@router.put("/update/{workbook_id}", auth=django_auth)
def update_workbook(request, workbook_id:int, payload:WorkbookUpdateSchema):
    if not request.user.is_authenticated:
        return JsonResponse({"status": "fail", "message": "Unauthorized"}, status=401)
    workbook = get_object_or_404(Workbook, id=workbook_id)
    for attr, value in payload.dict().items():
        setattr(workbook, attr, value)
    workbook.save()
    return JsonResponse({"status": "success", "message": "Workbook updated", "id": workbook.id},status=200)


# --- INSERT TRANSACTION ---
@router.post("{workbook_id}/entry/create")
def create_transaction(request, payload: TransactionCreateSchema, workbook_id:int):
    if not request.user.is_authenticated:
        return JsonResponse({"status": "fail", "message": "Unauthorized"}, status=401)

    # Ensure the workbook exists AND belongs to the requesting user
    workbook = get_object_or_404(Workbook, id=workbook_id, user=request.user)
    print(workbook)
    transaction = Transaction.objects.create(
        workbook=workbook,
        category=payload.category,
        amount=payload.amount,
        remarks=payload.remarks,
        nature=payload.nature,
        date=payload.date
    )
    return JsonResponse({"status": "success", "transaction_id": transaction.id}, status=201)


# --- EDIT TRANSACTION ---
@router.put("{workbook_id}/entry/update/{transaction_id}")
def update_transaction(request,workbook_id:int, transaction_id: int, payload: TransactionUpdateSchema):
    print(payload)
    if not request.user.is_authenticated:
        return JsonResponse({"status": "fail", "message": "Unauthorized"}, status=401)

    # Ensure the transaction exists AND the parent workbook belongs to the requesting user
    transaction = get_object_or_404(Transaction, workbook_id=workbook_id, id=transaction_id, workbook__user=request.user)

    # Update only the fields that were provided in the payload
    for attr, value in payload.dict(exclude_unset=True).items():
        setattr(transaction, attr, value)
    transaction.save()

    return JsonResponse({"status": "success", "message": "Transaction updated successfully"}, status=200)

@router.delete("{workbook_id}/entry/delete/{transaction_id}")
def delete_transaction(request, transaction_id:int, workbook_id:int):
    if not request.user.is_authenticated:
        return JsonResponse({"status": "fail", "message": "Unauthorized"}, status=401)
    deleted_transaction = get_object_or_404(Transaction, id=transaction_id)
    deleted_transaction.delete()
    return JsonResponse({"status": "success"}, status=200)