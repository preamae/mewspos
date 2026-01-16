<?php
/**
 * Mews POS PHP Gateway İşlemcisi
 * Bu dosya Odoo'dan gelen istekleri işler ve mewebstudio/pos kütüphanesini kullanır
 */

require_once __DIR__ . '/vendor/autoload.php';

use Mews\Pos\Factory\PosFactory;
use Mews\Pos\Factory\AccountFactory;
use Mews\Pos\Factory\CreditCardFactory;
use Mews\Pos\PosInterface;
use Symfony\Component\EventDispatcher\EventDispatcher;

class MewsPosProcessor
{
    private $config;
    private $eventDispatcher;
    
    public function __construct()
    {
        $this->eventDispatcher = new EventDispatcher();
        $this->loadConfig();
    }
    
    private function loadConfig()
    {
        $this->config = require __DIR__ . '/config/pos_config.php';
    }
    
    /**
     * Gateway oluştur
     */
    private function createGateway($bankConfig)
    {
        $account = $this->createAccount($bankConfig);
        
        return PosFactory::createPosGateway(
            $account,
            $this->config,
            $this->eventDispatcher
        );
    }
    
    /**
     * Banka hesabı oluştur
     */
    private function createAccount($bankConfig)
    {
        $gatewayType = $bankConfig['gateway_type'];
        $paymentModel = $this->mapPaymentModel($bankConfig['payment_model']);
        
        switch ($gatewayType) {
            case 'akbank_pos':
                return AccountFactory::createAkbankPosAccount(
                    $bankConfig['bank_code'],
                    $bankConfig['client_id'],
                    $bankConfig['username'],
                    $bankConfig['password'],
                    PosInterface::LANG_TR
                );
                
            case 'estv3_pos': 
                return AccountFactory::createEstPosAccount(
                    $bankConfig['bank_code'],
                    $bankConfig['client_id'],
                    $bankConfig['username'],
                    $bankConfig['password'],
                    $paymentModel,
                    $bankConfig['store_key'],
                    PosInterface::LANG_TR
                );
                
            case 'garanti_pos':
                return AccountFactory::createGarantiPosAccount(
                    $bankConfig['bank_code'],
                    $bankConfig['merchant_id'],
                    $bankConfig['username'],
                    $bankConfig['password'],
                    $bankConfig['terminal_id'],
                    $paymentModel,
                    $bankConfig['store_key']
                );
                
            case 'posnet':
                return AccountFactory::createPosNetAccount(
                    $bankConfig['bank_code'],
                    $bankConfig['merchant_id'],
                    $bankConfig['username'],
                    $bankConfig['store_key'],
                    $paymentModel,
                    $bankConfig['terminal_id']
                );
                
            case 'payfor':
                return AccountFactory::createPayForAccount(
                    $bankConfig['bank_code'],
                    $bankConfig['merchant_id'],
                    $bankConfig['username'],
                    $bankConfig['password'],
                    $paymentModel,
                    $bankConfig['store_key'],
                    PosInterface::LANG_TR
                );
                
            case 'payflex_mpi':
            case 'payflex_common': 
                return AccountFactory:: createPayFlexAccount(
                    $bankConfig['bank_code'],
                    $bankConfig['merchant_id'],
                    $bankConfig['password'],
                    $bankConfig['terminal_id'],
                    $paymentModel
                );
                
            case 'interpos':
                return AccountFactory::createInterPosAccount(
                    $bankConfig['bank_code'],
                    $bankConfig['client_id'],
                    $bankConfig['username'],
                    $bankConfig['password']
                );
                
            case 'kuveyt_pos':
                return AccountFactory::createKuveytPosAccount(
                    $bankConfig['bank_code'],
                    $bankConfig['merchant_id'],
                    $bankConfig['username'],
                    $bankConfig['password'],
                    $bankConfig['store_key'],
                    $paymentModel,
                    $bankConfig['terminal_id']
                );
                
            default:
                throw new \Exception("Desteklenmeyen gateway tipi: {$gatewayType}");
        }
    }
    
    /**
     * Ödeme modelini eşle
     */
    private function mapPaymentModel($model)
    {
        $mapping = [
            '3d_secure' => PosInterface::MODEL_3D_SECURE,
            '3d_pay' => PosInterface::MODEL_3D_PAY,
            '3d_host' => PosInterface::MODEL_3D_HOST,
            'non_secure' => PosInterface::MODEL_NON_SECURE,
        ];
        
        return $mapping[$model] ??  PosInterface::MODEL_3D_SECURE;
    }
    
    /**
     * 3D Secure form verisi oluştur
     */
    public function create3DFormData($request)
    {
        $bankConfig = $request['bank_config'];
        $pos = $this->createGateway($bankConfig);
        
        // Sipariş bilgileri
        $order = [
            'id' => $request['transaction_id'],
            'amount' => $request['amount'],
            'currency' => $this->mapCurrency($request['currency']),
            'installment' => $request['installment'],
            'success_url' => $request['success_url'],
            'fail_url' => $request['fail_url'],
            'lang' => PosInterface::LANG_TR,
        ];
        
        // Kredi kartı
        $card = CreditCardFactory::createForGateway(
            $pos,
            $request['card']['number'],
            $request['card']['year'],
            $request['card']['month'],
            $request['card']['cvv'],
            $request['card']['name']
        );
        
        // Form verisi oluştur
        $pos->prepare($order, PosInterface::TX_TYPE_PAY_AUTH);
        
        return $pos->get3DFormData(
            $bankConfig['endpoints']['gateway_3d'],
            $card
        );
    }
    
    /**
     * 3D Secure callback işle
     */
    public function process3DCallback($request)
    {
        $bankConfig = $request['bank_config'];
        $pos = $this->createGateway($bankConfig);
        
        $order = [
            'id' => $request['order_id'],
            'amount' => $request['amount'],
            'currency' => $this->mapCurrency($request['currency']),
            'installment' => $request['installment'],
        ];
        
        $pos->prepare($order, PosInterface::TX_TYPE_PAY_AUTH);
        
        // Banka yanıtını işle
        $pos->payment($_POST);
        
        $response = $pos->getResponse();
        
        return [
            'success' => $response['status'] === 'approved',
            'order_id' => $response['order_id'] ?? null,
            'auth_code' => $response['auth_code'] ?? null,
            'error_code' => $response['error_code'] ??  null,
            'error_message' => $response['error_message'] ?? null,
            'response' => $response,
        ];
    }
    
    /**
     * Non-Secure ödeme
     */
    public function processNonSecurePayment($request)
    {
        $bankConfig = $request['bank_config'];
        $pos = $this->createGateway($bankConfig);
        
        $order = [
            'id' => $request['transaction_id'],
            'amount' => $request['amount'],
            'currency' => $this->mapCurrency($request['currency']),
            'installment' => $request['installment'],
        ];
        
        $card = CreditCardFactory::createForGateway(
            $pos,
            $request['card']['number'],
            $request['card']['year'],
            $request['card']['month'],
            $request['card']['cvv'],
            $request['card']['name']
        );
        
        $pos->prepare($order, PosInterface::TX_TYPE_PAY_AUTH);
        $pos->payment($card);
        
        $response = $pos->getResponse();
        
        return [
            'success' => $response['status'] === 'approved',
            'order_id' => $response['order_id'] ?? null,
            'auth_code' => $response['auth_code'] ?? null,
            'error_code' => $response['error_code'] ?? null,
            'error_message' => $response['error_message'] ?? null,
            'response' => $response,
        ];
    }
    
    /**
     * İptal işlemi
     */
    public function processCancel($request)
    {
        $bankConfig = $request['bank_config'];
        $pos = $this->createGateway($bankConfig);
        
        $order = [
            'id' => $request['order_id'],
            'amount' => $request['amount'],
            'currency' => $this->mapCurrency($request['currency']),
        ];
        
        $pos->prepare($order, PosInterface::TX_TYPE_CANCEL);
        $pos->cancel();
        
        $response = $pos->getResponse();
        
        return [
            'success' => $response['status'] === 'approved',
            'response' => $response,
        ];
    }
    
    /**
     * İade işlemi
     */
    public function processRefund($request)
    {
        $bankConfig = $request['bank_config'];
        $pos = $this->createGateway($bankConfig);
        
        $order = [
            'id' => $request['order_id'],
            'amount' => $request['amount'],
            'currency' => $this->mapCurrency($request['currency']),
        ];
        
        $pos->prepare($order, PosInterface::TX_TYPE_REFUND);
        $pos->refund();
        
        $response = $pos->getResponse();
        
        return [
            'success' => $response['status'] === 'approved',
            'response' => $response,
        ];
    }
    
    /**
     * Para birimini eşle
     */
    private function mapCurrency($currency)
    {
        $mapping = [
            'TRY' => PosInterface::CURRENCY_TRY,
            'USD' => PosInterface:: CURRENCY_USD,
            'EUR' => PosInterface:: CURRENCY_EUR,
            'GBP' => PosInterface::CURRENCY_GBP,
        ];
        
        return $mapping[$currency] ?? PosInterface::CURRENCY_TRY;
    }
}

// API endpoint işleyici
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    header('Content-Type:  application/json; charset=utf-8');
    
    try {
        $input = json_decode(file_get_contents('php://input'), true);
        $action = $input['action'] ?? '';
        
        $processor = new MewsPosProcessor();
        
        switch ($action) {
            case 'create_3d_form': 
                $result = $processor->create3DFormData($input);
                break;
                
            case 'process_3d_callback': 
                $result = $processor->process3DCallback($input);
                break;
                
            case 'non_secure_payment': 
                $result = $processor->processNonSecurePayment($input);
                break;
                
            case 'cancel':
                $result = $processor->processCancel($input);
                break;
                
            case 'refund': 
                $result = $processor->processRefund($input);
                break;
                
            default:
                throw new \Exception("Bilinmeyen işlem:  {$action}");
        }
        
        echo json_encode(['success' => true, 'data' => $result]);
        
    } catch (\Exception $e) {
        http_response_code(500);
        echo json_encode([
            'success' => false,
            'error' => $e->getMessage(),
        ]);
    }
}