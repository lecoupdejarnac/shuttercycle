<?php

$mg = new MultimediaGallery();
$op = $_GET['op'];
if($op === 'display') {
   $req = $_GET['req'];
   $cursor = $_GET['cursor'];
   $folder = $_GET['folder'];
   $share = $_GET['share'] === '1';
   $mg->display($req, $cursor, $folder, $share);
}
elseif($op === 'getTotalFiles') {
   $folder = $_GET['folder'];
   $share = $_GET['share'] === '1';
   $mg->getTotalFiles($folder, $share);
}

class MultimediaGallery
{
   private $xsl_file = 'multimedia2text.xsl';
   private $xml_file = 'config.xml';
   private $xml_root = 'configs/';
   
   public function __construct()
   {}

   private function getConfigPath($folder, $share)
   {
      if($share) {
         return $this->xml_root . 'hidden/' . $folder . $this->xml_file;
      }
      return $this->xml_root . 'gallery/' . $folder . $this->xml_file;
   }
   
   public function display($req, $cursor, $folder, $share)
   {
      $doc = new DOMDocument();
      $xsl = new XSLTProcessor();

      $doc->load($this->xsl_file);
      $xsl->importStyleSheet($doc);
      
      $xsl->setParameter('', 'req', $req);
      $xsl->setParameter('', 'cursor', $cursor);
      
      $doc->load($this->getConfigPath($folder, $share));
      $json_str = $xsl->transformToXML($doc);
      $json_str = str_replace(',]', ']', $json_str);
      $json_str = str_replace(',}', '}', $json_str);
      echo $json_str;
   }
   
   public function getTotalFiles($folder, $share)
   {
      $doc = new DOMDocument();
      $doc->load($this->getConfigPath($folder, $share));
      $file = $doc->getElementsByTagName('file');
      $totalFiles = 0;
      foreach($file as $entry) {
         if($entry->getElementsByTagName('hidden')->length == 0)
            $totalFiles++;
      }
      echo $totalFiles;
   }
}
